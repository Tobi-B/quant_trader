"""Tests for StockDataProvider."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
import requests

from quant_trader.core.errors import ProviderError, RateLimitedError, TickerNotFoundError
from quant_trader.core.types import Granularity
from quant_trader.data.stockdata_provider import StockDataProvider


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.last_url: str | None = None
        self.last_params: dict[str, Any] | None = None

    def get(self, url: str, params: dict[str, Any] | None = None, timeout: int = 0) -> _FakeResponse:  # noqa: ARG002
        self.last_url = url
        self.last_params = params
        return self._response


def _eod_payload() -> dict[str, Any]:
    return {
        "meta": {"date_from": "2024-01-02", "date_to": "2024-01-05"},
        "data": [
            {"date": "2024-01-02T00:00:00.000Z", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000},
            {"date": "2024-01-03T00:00:00.000Z", "open": 101.0, "high": 102.0, "low": 100.0, "close": 101.5, "volume": 1500},
        ],
    }


def _intraday_payload() -> dict[str, Any]:
    return {
        "meta": {"date_from": "2024-01-02", "date_to": "2024-01-02"},
        "data": [
            {
                "date": "2024-01-02T16:00:00.000Z",
                "ticker": "SPY",
                "data": {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 500},
            },
            {
                "date": "2024-01-02T15:00:00.000Z",
                "ticker": "SPY",
                "data": {"open": 99.5, "high": 100.5, "low": 99.0, "close": 100.0, "volume": 400},
            },
        ],
    }


def test_stockdata_name() -> None:
    assert StockDataProvider().name == "stockdata"


def test_stockdata_missing_token_raises_provider_error() -> None:
    prov = StockDataProvider(api_token="")

    with pytest.raises(ProviderError) as exc:
        prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert "STOCKDATA_API_TOKEN not set" in str(exc.value)


def test_stockdata_daily_returns_bars() -> None:
    session = _FakeSession(_FakeResponse(200, _eod_payload()))
    prov = StockDataProvider(api_token="valid", session=session)  # type: ignore[arg-type]

    bars = prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)

    assert len(bars) == 2
    assert session.last_url is not None
    assert session.last_url.endswith("/data/eod")
    assert session.last_params is not None
    assert session.last_params["symbols"] == "SPY"
    assert session.last_params["interval"] == "day"
    assert session.last_params["sort"] == "asc"
    assert bars[0].open == 100.0
    assert bars[1].close == 101.5
    assert bars[0].adjusted_close == 100.5


def test_stockdata_intraday_uses_hour_interval() -> None:
    session = _FakeSession(_FakeResponse(200, _intraday_payload()))
    prov = StockDataProvider(api_token="valid", session=session)  # type: ignore[arg-type]

    bars = prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 2), Granularity.INTRADAY_60M)

    assert session.last_url is not None
    assert session.last_url.endswith("/data/intraday")
    assert session.last_params is not None
    assert session.last_params["interval"] == "hour"
    assert len(bars) == 2
    assert bars[0].timestamp.hour == 15
    assert bars[1].timestamp.hour == 16


def test_stockdata_intraday_15m_uses_minute_interval() -> None:
    session = _FakeSession(_FakeResponse(200, _intraday_payload()))
    prov = StockDataProvider(api_token="valid", session=session)  # type: ignore[arg-type]

    prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 2), Granularity.INTRADAY_15M)

    assert session.last_params is not None
    assert session.last_params["interval"] == "minute"


def test_stockdata_empty_data_raises_ticker_not_found() -> None:
    payload = {"meta": {}, "data": []}
    session = _FakeSession(_FakeResponse(200, payload))
    prov = StockDataProvider(api_token="valid", session=session)  # type: ignore[arg-type]

    with pytest.raises(TickerNotFoundError) as exc:
        prov.fetch("ZZZZZ", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert exc.value.ticker == "ZZZZZ"


def test_stockdata_http_429_raises_rate_limited() -> None:
    session = _FakeSession(_FakeResponse(429, {}))
    prov = StockDataProvider(api_token="valid", session=session)  # type: ignore[arg-type]

    with pytest.raises(RateLimitedError):
        prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)


def test_stockdata_http_401_raises_provider_error() -> None:
    session = _FakeSession(_FakeResponse(401, {}))
    prov = StockDataProvider(api_token="valid", session=session)  # type: ignore[arg-type]

    with pytest.raises(ProviderError) as exc:
        prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert "401" in str(exc.value)


def test_stockdata_network_error_raises_provider_error() -> None:
    class BrokenSession:
        def get(self, *args: object, **kwargs: object) -> _FakeResponse:
            raise requests.ConnectionError("offline")

    prov = StockDataProvider(api_token="valid", session=BrokenSession())  # type: ignore[arg-type]

    with pytest.raises(ProviderError) as exc:
        prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert "network error" in str(exc.value)


def test_stockdata_errors_field_raises_provider_error() -> None:
    payload = {"errors": ["invalid token"]}
    session = _FakeSession(_FakeResponse(200, payload))
    prov = StockDataProvider(api_token="valid", session=session)  # type: ignore[arg-type]

    with pytest.raises(ProviderError) as exc:
        prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert "invalid token" in str(exc.value)


def test_stockdata_bars_sorted_ascending() -> None:
    payload = {
        "meta": {},
        "data": [
            {"date": "2024-01-03T00:00:00.000Z", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100},
            {"date": "2024-01-02T00:00:00.000Z", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100},
        ],
    }
    session = _FakeSession(_FakeResponse(200, payload))
    prov = StockDataProvider(api_token="valid", session=session)  # type: ignore[arg-type]

    bars = prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)

    assert bars[0].timestamp.day == 2
    assert bars[1].timestamp.day == 3