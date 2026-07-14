"""Tests for FinancialModellingPrepProvider."""

from __future__ import annotations

from datetime import date, datetime
from typing import cast

import pytest
import requests

from quant_trader.core.errors import ProviderError, RateLimitedError, TickerNotFoundError
from quant_trader.core.types import Bar, Granularity
from quant_trader.data.financial_modelling_prep import FinancialModellingPrepProvider


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


class _BrokenSession:
    def get(self, url: str, timeout: int = 0) -> _FakeResponse:
        raise requests.ConnectionError("offline")


def _daily_row(day: str, value: float) -> dict[str, object]:
    return {
        "date": day,
        "open": value,
        "high": value + 1.0,
        "low": value - 1.0,
        "close": value + 0.5,
        "adjClose": value + 0.5,
        "volume": 1000,
    }


def _intraday_row(timestamp: str, value: float) -> dict[str, object]:
    row = _daily_row(timestamp, value)
    return row


def _provider(response: _FakeResponse) -> tuple[FinancialModellingPrepProvider, _FakeSession]:
    session = _FakeSession(response)
    provider = FinancialModellingPrepProvider(
        api_key="test-key", session=cast(requests.Session, session)
    )
    return provider, session


def test_fetch_daily_happy_path() -> None:
    payload = {
        "symbol": "SPY",
        "historical": [_daily_row("2024-01-03", 101.0), _daily_row("2024-01-02", 100.0)],
    }
    provider, session = _provider(_FakeResponse(200, payload))

    bars = provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert isinstance(bars, list)
    assert all(isinstance(bar, Bar) for bar in bars)
    assert [bar.timestamp for bar in bars] == [
        datetime(2024, 1, 2, 16),
        datetime(2024, 1, 3, 16),
    ]
    assert session.last_url == (
        "https://financialmodelingprep.com/api/v3/historical-price-full/SPY"
        "?from=2024-01-02&to=2024-01-03&apikey=test-key"
    )
    assert session.last_timeout == 30


def test_fetch_60m_happy_path() -> None:
    payload = {
        "symbol": "SPY",
        "historical": [_intraday_row("2024-01-02 10:00:00", 100.0)],
    }
    provider, session = _provider(_FakeResponse(200, payload))

    bars = provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 2), Granularity.INTRADAY_60M)

    assert len(bars) == 1
    assert bars[0].timestamp == datetime(2024, 1, 2, 10)
    assert session.last_url is not None
    assert "/historical-chart/1hour/SPY?" in session.last_url


def test_fetch_15m_happy_path() -> None:
    payload = {
        "symbol": "SPY",
        "historical": [_intraday_row("2024-01-02 10:15:00", 100.0)],
    }
    provider, session = _provider(_FakeResponse(200, payload))

    bars = provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 2), Granularity.INTRADAY_15M)

    assert len(bars) == 1
    assert bars[0].timestamp == datetime(2024, 1, 2, 10, 15)
    assert session.last_url is not None
    assert "/historical-chart/15min/SPY?" in session.last_url


def test_empty_historical_raises_ticker_not_found() -> None:
    provider, _ = _provider(_FakeResponse(200, {"symbol": "ZZZZ", "historical": []}))

    with pytest.raises(TickerNotFoundError) as exc:
        provider.fetch("ZZZZ", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert exc.value.ticker == "ZZZZ"


def test_invalid_api_key_raises_provider_error() -> None:
    provider, _ = _provider(_FakeResponse(200, {"Error Message": "Invalid API KEY."}))

    with pytest.raises(ProviderError) as exc:
        provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert "Invalid API KEY." in str(exc.value)


def test_rate_limit_raises_rate_limited() -> None:
    provider, _ = _provider(_FakeResponse(200, {"Error Message": "Limit Reach ..."}))

    with pytest.raises(RateLimitedError) as exc:
        provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert "Limit Reach" in str(exc.value)


def test_http_429_raises_rate_limited() -> None:
    provider, _ = _provider(_FakeResponse(429, {}))

    with pytest.raises(RateLimitedError) as exc:
        provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert "HTTP 429" in str(exc.value)


def test_http_500_raises_provider_error() -> None:
    provider, _ = _provider(_FakeResponse(500, {}))

    with pytest.raises(ProviderError) as exc:
        provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert "HTTP 500" in str(exc.value)


def test_network_error_raises_provider_error() -> None:
    provider = FinancialModellingPrepProvider(
        api_key="test-key",
        session=cast(requests.Session, _BrokenSession()),
    )

    with pytest.raises(ProviderError) as exc:
        provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert "network: offline" in str(exc.value)


def test_no_api_key_raises_provider_error() -> None:
    provider = FinancialModellingPrepProvider(api_key="")

    with pytest.raises(ProviderError) as exc:
        provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert "FINANCIAL_MODELLING_PREP_KEY not set" in str(exc.value)


def test_date_filter_excludes_out_of_range() -> None:
    payload = {
        "symbol": "SPY",
        "historical": [
            _daily_row("2024-01-01", 99.0),
            _daily_row("2024-01-02", 100.0),
            _daily_row("2024-01-04", 103.0),
        ],
    }
    provider, _ = _provider(_FakeResponse(200, payload))

    bars = provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert [bar.timestamp.date() for bar in bars] == [date(2024, 1, 2)]


def test_camelcase_adjclose_mapped() -> None:
    payload = {"symbol": "SPY", "historical": [_daily_row("2024-01-02", 100.0)]}
    provider, _ = _provider(_FakeResponse(200, payload))

    bars = provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 2), Granularity.DAILY)

    assert bars[0].adjusted_close == 100.5
