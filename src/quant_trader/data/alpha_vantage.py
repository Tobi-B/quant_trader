"""Alpha Vantage implementation of DataProvider."""

from __future__ import annotations

import os
from datetime import date, datetime

import requests

from quant_trader.core.errors import (
    ProviderError,
    RateLimitedError,
    TickerNotFoundError,
)
from quant_trader.core.types import Bar, Granularity


_API_URL = "https://www.alphavantage.co/query"
_FUNCTION_MAP: dict[Granularity, str] = {
    Granularity.DAILY: "TIME_SERIES_DAILY_ADJUSTED",
    Granularity.INTRADAY_60M: "TIME_SERIES_INTRADAY",
    Granularity.INTRADAY_15M: "TIME_SERIES_INTRADAY",
}
_INTERVAL_PARAM: dict[Granularity, str] = {
    Granularity.INTRADAY_60M: "60min",
    Granularity.INTRADAY_15M: "15min",
}


class AlphaVantageProvider:
    name = "alphavantage"

    def __init__(self, api_key: str | None = None, session: requests.Session | None = None) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get("ALPHAVANTAGE_KEY", "")
        self._session = session or requests.Session()

    def fetch(
        self,
        ticker: str,
        start: date,
        end: date,
        granularity: Granularity,
    ) -> list[Bar]:
        if not self._api_key:
            raise ProviderError(self.name, "ALPHAVANTAGE_KEY not set")

        params: dict[str, str] = {
            "function": _FUNCTION_MAP[granularity],
            "symbol": ticker,
            "apikey": self._api_key,
            "outputsize": "full",
            "datatype": "json",
        }
        if granularity in _INTERVAL_PARAM:
            params["interval"] = _INTERVAL_PARAM[granularity]

        try:
            resp = self._session.get(_API_URL, params=params, timeout=30)
        except requests.RequestException as exc:
            raise ProviderError(self.name, f"network error: {exc}") from exc

        if resp.status_code == 429:
            raise RateLimitedError(self.name, "HTTP 429")
        if resp.status_code != 200:
            raise ProviderError(self.name, f"HTTP {resp.status_code}")

        payload = resp.json()

        if "Note" in payload:
            note = payload["Note"].lower()
            if "call frequency" in note or "premium" in note:
                raise RateLimitedError(self.name, payload["Note"])
            raise ProviderError(self.name, payload["Note"])

        if "Information" in payload:
            info = payload["Information"].lower()
            if "call frequency" in info or "premium" in info:
                raise RateLimitedError(self.name, payload["Information"])
            raise ProviderError(self.name, payload["Information"])

        if "Error Message" in payload:
            msg = payload["Error Message"].lower()
            if "invalid api call" in msg or "not found" in msg:
                raise TickerNotFoundError(ticker)
            raise ProviderError(self.name, payload["Error Message"])

        series_key = _series_key(granularity, payload)
        if series_key is None or series_key not in payload:
            raise TickerNotFoundError(ticker)

        return _parse_series(payload[series_key], granularity, start, end)


def _series_key(granularity: Granularity, payload: dict[str, object]) -> str | None:
    if granularity == Granularity.DAILY:
        return "Time Series (Daily)"
    if granularity == Granularity.INTRADAY_60M:
        return "Time Series (60min)"
    if granularity == Granularity.INTRADAY_15M:
        return "Time Series (15min)"
    for key in payload:
        if isinstance(key, str) and key.startswith("Time Series"):
            return key
    return None


def _parse_series(
    series: dict[str, dict[str, str]],
    granularity: Granularity,
    start: date,
    end: date,
) -> list[Bar]:
    bars: list[Bar] = []
    for ts_str, row in series.items():
        ts = _parse_timestamp(ts_str)
        if ts.date() < start or ts.date() > end:
            continue
        if granularity == Granularity.DAILY:
            bars.append(
                Bar(
                    timestamp=ts,
                    open=_f(row, "1. open"),
                    high=_f(row, "2. high"),
                    low=_f(row, "3. low"),
                    close=_f(row, "4. close"),
                    adjusted_close=_f(row, "5. adjusted close"),
                    volume=_i(row, "6. volume"),
                )
            )
        else:
            bars.append(
                Bar(
                    timestamp=ts,
                    open=_f(row, "1. open"),
                    high=_f(row, "2. high"),
                    low=_f(row, "3. low"),
                    close=_f(row, "4. close"),
                    adjusted_close=_f(row, "5. adjusted close"),
                    volume=_i(row, "5. volume"),
                )
            )
    bars.sort(key=lambda b: b.timestamp)
    return bars


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace(" ", "T"))


def _f(row: dict[str, str], key: str) -> float:
    return float(row[key])


def _i(row: dict[str, str], key: str) -> int:
    return int(float(row[key]))