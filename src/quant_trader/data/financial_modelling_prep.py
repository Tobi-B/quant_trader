"""Financial Modelling Prep implementation of DataProvider."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import date, datetime
from typing import ClassVar, cast

import requests

from quant_trader.core.errors import ProviderError, RateLimitedError, TickerNotFoundError
from quant_trader.core.types import Bar, Granularity

_BASE_URL = "https://financialmodelingprep.com/api/v3"
_ENDPOINT_MAP: dict[Granularity, str] = {
    Granularity.DAILY: "historical-price-full",
    Granularity.INTRADAY_60M: "historical-chart/1hour",
    Granularity.INTRADAY_15M: "historical-chart/15min",
}


class FinancialModellingPrepProvider:
    """Fetch historical bars from Financial Modeling Prep."""

    name: ClassVar[str] = "fmp"

    def __init__(self, api_key: str | None = None, session: requests.Session | None = None) -> None:
        self._api_key = (
            api_key if api_key is not None else os.environ.get("FINANCIAL_MODELLING_PREP_KEY", "")
        )
        self._session = session if session is not None else requests.Session()

    def fetch(
        self,
        ticker: str,
        start: date,
        end: date,
        granularity: Granularity,
    ) -> list[Bar]:
        if not self._api_key:
            raise ProviderError(self.name, "FINANCIAL_MODELLING_PREP_KEY not set")

        endpoint = _ENDPOINT_MAP[granularity]
        url = (
            f"{_BASE_URL}/{endpoint}/{ticker}"
            f"?from={start.isoformat()}&to={end.isoformat()}&apikey={self._api_key}"
        )

        try:
            response = self._session.get(url, timeout=30)
        except requests.RequestException as exc:
            raise ProviderError(self.name, f"network: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitedError(self.name, "HTTP 429")
        if response.status_code != 200:
            raise ProviderError(self.name, f"HTTP {response.status_code}")

        payload = cast(object, response.json())
        if not isinstance(payload, dict):
            raise ProviderError(self.name, "invalid JSON response")
        response_data: Mapping[str, object] = cast(Mapping[str, object], payload)

        error_message = response_data.get("Error Message")
        if isinstance(error_message, str):
            uppercase_message = error_message.upper()
            if "INVALID API" in uppercase_message or "API KEY" in uppercase_message:
                raise ProviderError(self.name, error_message)
            if "LIMIT" in uppercase_message:
                raise RateLimitedError(self.name, error_message)
            raise ProviderError(self.name, error_message)

        historical = response_data.get("historical")
        if not isinstance(historical, list):
            raise TickerNotFoundError(ticker)
        if not historical:
            raise TickerNotFoundError(ticker)

        return _parse_historical(historical, granularity, start, end)


def _parse_historical(
    historical: list[object],
    granularity: Granularity,
    start: date,
    end: date,
) -> list[Bar]:
    bars: list[Bar] = []
    for raw_row in historical:
        if not isinstance(raw_row, dict):
            continue
        row: Mapping[str, object] = cast(Mapping[str, object], raw_row)
        date_value = row.get("date")
        if not isinstance(date_value, str):
            continue
        timestamp = _parse_timestamp(date_value, granularity)
        if timestamp.date() < start or timestamp.date() > end:
            continue
        bars.append(
            Bar(
                timestamp=timestamp,
                open=_float(row, "open"),
                high=_float(row, "high"),
                low=_float(row, "low"),
                close=_float(row, "close"),
                adjusted_close=_float(row, "adjClose"),
                volume=_int(row, "volume"),
            )
        )
    bars.sort(key=lambda bar: bar.timestamp)
    return bars


def _parse_timestamp(value: str, granularity: Granularity) -> datetime:
    if granularity == Granularity.DAILY:
        return datetime.fromisoformat(f"{value}T16:00:00")
    return datetime.fromisoformat(value)


def _float(row: Mapping[str, object], key: str) -> float:
    value = row[key]
    if not isinstance(value, (int, float, str)):
        raise ValueError(f"FMP field {key} is not numeric")
    return float(value)


def _int(row: Mapping[str, object], key: str) -> int:
    value = row[key]
    if not isinstance(value, (int, float, str)):
        raise ValueError(f"FMP field {key} is not numeric")
    return int(float(value))
