"""Stockdata.org implementation of DataProvider."""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

import requests

from quant_trader.core.errors import (
    ProviderError,
    RateLimitedError,
    TickerNotFoundError,
)
from quant_trader.core.types import Bar, Granularity


_API_BASE = "https://api.stockdata.org/v1"
_INTERVAL_MAP: dict[Granularity, str] = {
    Granularity.INTRADAY_60M: "hour",
    Granularity.INTRADAY_15M: "minute",
}


class StockDataProvider:
    name = "stockdata"

    def __init__(
        self,
        api_token: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self._api_token = (
            api_token if api_token is not None else os.environ.get("STOCKDATA_API_TOKEN", "")
        )
        self._session = session or requests.Session()

    def fetch(
        self,
        ticker: str,
        start: date,
        end: date,
        granularity: Granularity,
    ) -> list[Bar]:
        if not self._api_token:
            raise ProviderError(self.name, "STOCKDATA_API_TOKEN not set")

        if granularity == Granularity.DAILY:
            url = f"{_API_BASE}/data/eod"
            params: dict[str, str] = {
                "api_token": self._api_token,
                "symbols": ticker,
                "date_from": start.isoformat(),
                "date_to": end.isoformat(),
                "interval": "day",
                "sort": "asc",
            }
        else:
            url = f"{_API_BASE}/data/intraday"
            params = {
                "api_token": self._api_token,
                "symbols": ticker,
                "date_from": start.isoformat(),
                "date_to": end.isoformat(),
                "interval": _INTERVAL_MAP[granularity],
                "sort": "asc",
            }

        try:
            resp = self._session.get(url, params=params, timeout=30)
        except requests.RequestException as exc:
            raise ProviderError(self.name, f"network error: {exc}") from exc

        if resp.status_code == 429:
            raise RateLimitedError(self.name, "HTTP 429")
        if resp.status_code == 401:
            raise ProviderError(self.name, "HTTP 401 unauthorized")
        if resp.status_code != 200:
            raise ProviderError(self.name, f"HTTP {resp.status_code}")

        payload = resp.json()

        if "errors" in payload:
            raise ProviderError(self.name, str(payload["errors"]))

        entries = payload.get("data") or []
        if not entries:
            raise TickerNotFoundError(ticker)

        bars = [_entry_to_bar(entry, granularity) for entry in entries]
        bars.sort(key=lambda b: b.timestamp)
        return bars


def _entry_to_bar(entry: dict[str, Any], granularity: Granularity) -> Bar:
    if "data" in entry and isinstance(entry["data"], dict):
        ohlcv = entry["data"]
    else:
        ohlcv = entry

    close = float(ohlcv["close"])
    return Bar(
        timestamp=_parse_date(entry["date"], granularity),
        open=float(ohlcv["open"]),
        high=float(ohlcv["high"]),
        low=float(ohlcv["low"]),
        close=close,
        adjusted_close=close,
        volume=int(ohlcv["volume"]),
    )


def _parse_date(value: str, granularity: Granularity) -> datetime:
    text = value.replace("Z", "+00:00")
    ts = datetime.fromisoformat(text)
    if granularity == Granularity.DAILY:
        return ts.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    return ts.replace(tzinfo=None)