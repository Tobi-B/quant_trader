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
from quant_trader.data.instrument_search import CompanySearchService


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

    def get(self, url: str, timeout: int = 0) -> _FakeResponse:
        self.last_url = url
        self.last_timeout = timeout
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
