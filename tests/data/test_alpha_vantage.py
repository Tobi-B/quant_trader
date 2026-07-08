"""Tests for AlphaVantageProvider."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
import requests

from quant_trader.core.errors import ProviderError, RateLimitedError, TickerNotFoundError
from quant_trader.core.types import Granularity
from quant_trader.data.alpha_vantage import AlphaVantageProvider


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


def _daily_payload() -> dict[str, Any]:
    return {
        "Meta Data": {"1. Information": "Daily Prices"},
        "Time Series (Daily)": {
            "2024-01-02": {
                "1. open": "100.0",
                "2. high": "101.0",
                "3. low": "99.0",
                "4. close": "100.5",
                "5. adjusted close": "100.5",
                "6. volume": "1000",
            },
            "2024-01-03": {
                "1. open": "101.0",
                "2. high": "102.0",
                "3. low": "100.0",
                "4. close": "101.5",
                "5. adjusted close": "101.5",
                "6. volume": "1500",
            },
        },
    }


def test_av_missing_key_raises_provider_error() -> None:
    prov = AlphaVantageProvider(api_key="")

    with pytest.raises(ProviderError) as exc:
        prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert "ALPHAVANTAGE_KEY not set" in str(exc.value)


def test_av_returns_bars_daily() -> None:
    session = _FakeSession(_FakeResponse(200, _daily_payload()))
    prov = AlphaVantageProvider(api_key="valid", session=session)  # type: ignore[arg-type]

    bars = prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)

    assert len(bars) == 2
    assert session.last_params is not None
    assert session.last_params["function"] == "TIME_SERIES_DAILY_ADJUSTED"
    assert session.last_params["symbol"] == "SPY"
    assert session.last_params["apikey"] == "valid"
    assert bars[0].open == 100.0
    assert bars[1].volume == 1500


def test_av_invalid_call_raises_ticker_not_found() -> None:
    payload = {"Error Message": "Invalid API call."}
    session = _FakeSession(_FakeResponse(200, payload))
    prov = AlphaVantageProvider(api_key="valid", session=session)  # type: ignore[arg-type]

    with pytest.raises(TickerNotFoundError) as exc:
        prov.fetch("ZZZZZ", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert exc.value.ticker == "ZZZZZ"


def test_av_rate_limit_note_raises_rate_limited_error() -> None:
    payload = {"Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 25 requests per day."}
    session = _FakeSession(_FakeResponse(200, payload))
    prov = AlphaVantageProvider(api_key="valid", session=session)  # type: ignore[arg-type]

    with pytest.raises(RateLimitedError):
        prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)


def test_av_http_429_raises_rate_limited_error() -> None:
    session = _FakeSession(_FakeResponse(429, {}))
    prov = AlphaVantageProvider(api_key="valid", session=session)  # type: ignore[arg-type]

    with pytest.raises(RateLimitedError):
        prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)


def test_av_http_500_raises_provider_error() -> None:
    session = _FakeSession(_FakeResponse(500, {}))
    prov = AlphaVantageProvider(api_key="valid", session=session)  # type: ignore[arg-type]

    with pytest.raises(ProviderError) as exc:
        prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert "500" in str(exc.value)


def test_av_network_error_raises_provider_error() -> None:
    class BrokenSession:
        def get(self, *args: object, **kwargs: object) -> _FakeResponse:
            raise requests.ConnectionError("offline")

    prov = AlphaVantageProvider(api_key="valid", session=BrokenSession())  # type: ignore[arg-type]

    with pytest.raises(ProviderError) as exc:
        prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert "network error" in str(exc.value)


def test_av_missing_series_raises_ticker_not_found() -> None:
    payload: dict[str, Any] = {"Meta Data": {}}
    session = _FakeSession(_FakeResponse(200, payload))
    prov = AlphaVantageProvider(api_key="valid", session=session)  # type: ignore[arg-type]

    with pytest.raises(TickerNotFoundError):
        prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)