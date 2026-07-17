"""Tests for instrument search providers and service."""

from __future__ import annotations

from typing import cast

import pytest
import requests

from quant_trader.core.errors import (
    DataError,
    ProviderError,
    RateLimitedError,
    SearchUnavailableError,
)
from quant_trader.core.types import Instrument
from quant_trader.data.financial_modelling_prep import FinancialModellingPrepProvider
from quant_trader.data.instrument_search import (
    CompanySearchService,
    FmpProfilePhantomValidator,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        return self._payload


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.last_url: str | None = None
        self.last_timeout: int | None = None
        self.last_params: dict[str, str] | None = None

    def get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        timeout: int = 0,
    ) -> _FakeResponse:
        self.last_url = url
        self.last_timeout = timeout
        self.last_params = params
        return self._response


class _SearchProvider:
    def __init__(self, result: list[Instrument] | Exception) -> None:
        self._result = result
        self.calls: list[tuple[str, int, str | None]] = []

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        exchange: str | None = None,
    ) -> list[Instrument]:
        self.calls.append((query, limit, exchange))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _provider(response: _FakeResponse) -> tuple[FinancialModellingPrepProvider, _FakeSession]:
    session = _FakeSession(response)
    provider = FinancialModellingPrepProvider(
        api_key="test-key", session=cast(requests.Session, session)
    )
    return provider, session


def test_fmp_search_parses_instruments() -> None:
    provider, session = _provider(
        _FakeResponse(
            200,
            [
                {
                    "symbol": "aapl",
                    "name": "Apple Inc.",
                    "exchange": "NASDAQ",
                    "exchangeFullName": "NASDAQ Global Select",
                    "currency": "USD",
                },
                {"symbol": "MSFT", "name": "Microsoft Corporation", "exchange": "NASDAQ"},
                {"symbol": "", "name": "Invalid"},
            ],
        )
    )

    results = provider.search("Apple")

    assert results == [
        Instrument("AAPL", "Apple Inc.", "NASDAQ", "USD"),
        Instrument("MSFT", "Microsoft Corporation", "NASDAQ", ""),
    ]
    assert session.last_url == (
        "https://financialmodelingprep.com/stable/search-name?query=Apple&limit=20&apikey=test-key"
    )
    assert session.last_timeout == 30


def test_fmp_search_encodes_query_and_bounds_limit() -> None:
    provider, session = _provider(_FakeResponse(200, []))

    provider.search(" Microsoft Corp ", limit=200, exchange="NASDAQ")

    assert session.last_url == (
        "https://financialmodelingprep.com/stable/search-name?"
        "query=Microsoft+Corp&limit=100&exchange=NASDAQ&apikey=test-key"
    )


def test_fmp_search_returns_empty_for_empty_query_without_request() -> None:
    provider, session = _provider(_FakeResponse(200, []))

    assert provider.search("   ") == []
    assert session.last_url is None


def test_fmp_search_raises_for_rate_limit() -> None:
    provider, _ = _provider(_FakeResponse(429, {}))

    with pytest.raises(RateLimitedError):
        provider.search("Apple")


def test_fmp_search_raises_for_invalid_payload() -> None:
    provider, _ = _provider(_FakeResponse(200, {"unexpected": "payload"}))

    with pytest.raises(ProviderError):
        provider.search("Apple")


def test_fmp_search_requires_api_key() -> None:
    provider = FinancialModellingPrepProvider(api_key="")

    with pytest.raises(ProviderError, match="FINANCIAL_MODELLING_PREP_KEY not set"):
        provider.search("Apple")


def test_company_search_service_returns_provider_results() -> None:
    expected = [Instrument("AAPL", "Apple Inc.", "NASDAQ", "USD")]
    provider = _SearchProvider(expected)
    service = CompanySearchService(provider)

    results = service.search("  Apple  ", limit=500)

    assert results == expected
    assert provider.calls == [("Apple", 100, None)]


def test_company_search_service_skips_empty_query() -> None:
    provider = _SearchProvider([])
    service = CompanySearchService(provider)

    assert service.search("  ") == []
    assert provider.calls == []


def test_company_search_service_maps_data_error() -> None:
    provider = _SearchProvider(DataError("offline"))
    service = CompanySearchService(provider)

    with pytest.raises(SearchUnavailableError) as exc:
        service.search("Apple")

    assert exc.value.query == "Apple"
    assert exc.value.reason == "Suchdienst nicht verfügbar"


def test_company_search_service_preserves_no_results() -> None:
    provider = _SearchProvider([])
    service = CompanySearchService(provider)

    assert service.search("unknown") == []


class _FakeValidator:
    def __init__(
        self,
        decisions: dict[str, bool] | None = None,
        exc: Exception | None = None,
    ) -> None:
        self._decisions = decisions or {}
        self._exc = exc
        self.calls: list[str] = []

    def is_real(self, symbol: str) -> bool:
        self.calls.append(symbol)
        if self._exc is not None:
            raise self._exc
        return self._decisions.get(symbol, True)


def test_company_search_service_filters_phantoms() -> None:
    results = [
        Instrument("AAPL.DE", "Apple Inc.", "XETRA", "EUR"),
        Instrument("APC.DE", "Apple Inc.", "XETRA", "EUR"),
        Instrument("AAPL", "Apple Inc.", "NASDAQ", "USD"),
    ]
    provider = _SearchProvider(results)
    validator = _FakeValidator(
        {"AAPL.DE": False, "APC.DE": True, "AAPL": True},
    )
    service = CompanySearchService(provider, phantom_validator=validator)

    kept = service.search("apple")

    assert kept == [
        Instrument("APC.DE", "Apple Inc.", "XETRA", "EUR"),
        Instrument("AAPL", "Apple Inc.", "NASDAQ", "USD"),
    ]
    assert validator.calls == ["AAPL.DE", "APC.DE", "AAPL"]


def test_company_search_service_validator_error_keeps_result() -> None:
    results = [Instrument("AAPL", "Apple Inc.", "NASDAQ", "USD")]
    provider = _SearchProvider(results)
    validator = _FakeValidator(exc=ProviderError("fmp", "HTTP 503"))
    service = CompanySearchService(provider, phantom_validator=validator)

    kept = service.search("apple")

    assert kept == results


def test_company_search_service_no_validator_returns_all() -> None:
    results = [
        Instrument("AAPL.DE", "Apple Inc.", "XETRA", "EUR"),
        Instrument("AAPL", "Apple Inc.", "NASDAQ", "USD"),
    ]
    provider = _SearchProvider(results)
    service = CompanySearchService(provider)

    assert service.search("apple") == results


def test_fmp_phantom_validator_flags_null_price() -> None:
    validator = FmpProfilePhantomValidator(
        api_key="k",
        session=cast(
            requests.Session,
            _FakeSession(
                _FakeResponse(
                    200,
                    [
                        {
                            "symbol": "AAPL.DE",
                            "price": None,
                            "marketCap": 0,
                            "volume": 0,
                        }
                    ],
                )
            ),
        ),
    )

    assert validator.is_real("AAPL.DE") is False


def test_fmp_phantom_validator_flags_zero_volume() -> None:
    validator = FmpProfilePhantomValidator(
        api_key="k",
        session=cast(
            requests.Session,
            _FakeSession(
                _FakeResponse(
                    200,
                    [
                        {
                            "symbol": "APC.DE",
                            "price": 291.65,
                            "marketCap": 1,
                            "volume": 0,
                        }
                    ],
                )
            ),
        ),
    )

    assert validator.is_real("APC.DE") is False


def test_fmp_phantom_validator_accepts_real_listing() -> None:
    validator = FmpProfilePhantomValidator(
        api_key="k",
        session=cast(
            requests.Session,
            _FakeSession(
                _FakeResponse(
                    200,
                    [
                        {
                            "symbol": "APC.DE",
                            "price": 291.65,
                            "marketCap": 4_283_567_377_400,
                            "volume": 49_810,
                        }
                    ],
                )
            ),
        ),
    )

    assert validator.is_real("APC.DE") is True


def test_fmp_phantom_validator_returns_false_for_empty_profile() -> None:
    validator = FmpProfilePhantomValidator(
        api_key="k",
        session=cast(requests.Session, _FakeSession(_FakeResponse(200, []))),
    )

    assert validator.is_real("ZZZZ.DE") is False


def test_fmp_phantom_validator_returns_true_without_api_key() -> None:
    validator = FmpProfilePhantomValidator(api_key="")

    assert validator.is_real("AAPL.DE") is True


def test_fmp_phantom_validator_raises_for_network_error() -> None:
    class _BrokenSession:
        def get(
            self, url: str, params: dict[str, str] | None = None, timeout: int = 0
        ) -> _FakeResponse:
            raise requests.ConnectionError("offline")

    validator = FmpProfilePhantomValidator(
        api_key="k",
        session=cast(requests.Session, _BrokenSession()),
    )

    with pytest.raises(ProviderError, match="network"):
        validator.is_real("AAPL.DE")


def test_fmp_phantom_validator_raises_for_rate_limit() -> None:
    validator = FmpProfilePhantomValidator(
        api_key="k",
        session=cast(requests.Session, _FakeSession(_FakeResponse(429, {}))),
    )

    with pytest.raises(ProviderError, match="HTTP 429"):
        validator.is_real("AAPL.DE")
