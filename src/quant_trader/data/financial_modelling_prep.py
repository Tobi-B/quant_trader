"""Financial Modelling Prep implementation of DataProvider."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import date, datetime
from typing import ClassVar, cast
from urllib.parse import urlencode

import requests

from quant_trader.core.errors import ProviderError, RateLimitedError, TickerNotFoundError
from quant_trader.core.logging import get_logger
from quant_trader.core.types import Bar, ExchangeDescriptor, Granularity, Instrument

log = get_logger(__name__)

_BASE_URL = "https://financialmodelingprep.com/stable"
_SEARCH_ENDPOINT = "search-name"
_EOD_ENDPOINT = "historical-price-eod/full"
_INTRADAY_ENDPOINT_MAP: dict[Granularity, str] = {
    Granularity.INTRADAY_60M: "historical-chart/1hour",
    Granularity.INTRADAY_15M: "historical-chart/15min",
}
_STOCK_LIST_ENDPOINT = "stock-list"
_ETF_LIST_ENDPOINT = "etf-list"
_FUND_LIST_ENDPOINT = "financial-statement-symbol-list"
_INDEX_LIST_ENDPOINT = "index-list"
_CRYPTO_LIST_ENDPOINT = "cryptocurrency-list"
_EXCHANGES_ENDPOINT = "available-exchanges"
_SECTORS_ENDPOINT = "available-sectors"
_COUNTRIES_ENDPOINT = "available-countries"
_INDEX_CONSTITUENT_ENDPOINT_MAP: dict[str, str] = {
    "sp500": "sp500-constituent",
    "nasdaq": "nasdaq-constituent",
    "dowjones": "dowjones-constituent",
}


class FinancialModellingPrepProvider:
    """Fetch historical bars from Financial Modeling Prep."""

    name: ClassVar[str] = "fmp"

    def __init__(self, api_key: str | None = None, session: requests.Session | None = None) -> None:
        self._api_key = (
            api_key if api_key is not None else os.environ.get("FINANCIAL_MODELLING_PREP_KEY", "")
        )
        self._session = session if session is not None else requests.Session()

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        exchange: str | None = None,
    ) -> list[Instrument]:
        if not self._api_key:
            raise ProviderError(self.name, "FINANCIAL_MODELLING_PREP_KEY not set")

        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        params = [
            ("query", cleaned_query),
            ("limit", str(max(1, min(limit, 100)))),
        ]
        if exchange:
            params.append(("exchange", exchange.strip()))
        params.append(("apikey", self._api_key))
        url = f"{_BASE_URL}/{_SEARCH_ENDPOINT}?{urlencode(params)}"

        try:
            response = self._session.get(url, timeout=30)
        except requests.RequestException as exc:
            raise ProviderError(self.name, f"network: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitedError(self.name, "HTTP 429")
        if response.status_code != 200:
            raise ProviderError(self.name, f"HTTP {response.status_code}")

        payload = cast(object, response.json())
        if isinstance(payload, dict):
            response_data: Mapping[str, object] = cast(Mapping[str, object], payload)
            error_message = response_data.get("Error Message")
            if isinstance(error_message, str):
                raise ProviderError(self.name, error_message)
            raise ProviderError(self.name, "invalid JSON response")
        if not isinstance(payload, list):
            raise ProviderError(self.name, "invalid JSON response")
        return _parse_search_results(payload)

    def fetch(
        self,
        ticker: str,
        start: date,
        end: date,
        granularity: Granularity,
    ) -> list[Bar]:
        if not self._api_key:
            raise ProviderError(self.name, "FINANCIAL_MODELLING_PREP_KEY not set")

        if granularity == Granularity.DAILY:
            url = (
                f"{_BASE_URL}/{_EOD_ENDPOINT}"
                f"?symbol={ticker}&from={start.isoformat()}&to={end.isoformat()}"
                f"&apikey={self._api_key}"
            )
        else:
            endpoint = _INTRADAY_ENDPOINT_MAP[granularity]
            url = (
                f"{_BASE_URL}/{endpoint}"
                f"?symbol={ticker}&from={start.isoformat()}&to={end.isoformat()}"
                f"&apikey={self._api_key}"
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
        if isinstance(payload, dict):
            response_data: Mapping[str, object] = cast(Mapping[str, object], payload)
            error_message = response_data.get("Error Message")
            if isinstance(error_message, str):
                uppercase_message = error_message.upper()
                if "INVALID API" in uppercase_message or "API KEY" in uppercase_message:
                    raise ProviderError(self.name, error_message)
                if "LIMIT" in uppercase_message:
                    raise RateLimitedError(self.name, error_message)
                raise ProviderError(self.name, error_message)
            raise ProviderError(self.name, "invalid JSON response")
        if not isinstance(payload, list):
            raise ProviderError(self.name, "invalid JSON response")
        if not payload:
            raise TickerNotFoundError(ticker)
        return _parse_historical(payload, granularity, start, end)

    def fetch_stock_list(self) -> list[Instrument]:
        payload = self._get_list(_STOCK_LIST_ENDPOINT)
        return _parse_instrument_list(payload, instrument_type="stock")

    def fetch_etf_list(self) -> list[Instrument]:
        payload = self._get_list(_ETF_LIST_ENDPOINT)
        return _parse_instrument_list(payload, instrument_type="etf")

    def fetch_fund_list(self) -> list[Instrument]:
        """Mutual funds are not part of the FMP free tier.

        The endpoint returns HTTP 401/403 (or an empty list) on the free
        tier; that is treated as "not available", not as a provider
        failure, since we know upfront it's an honest scope gap (see
        ADR-0018) rather than a transient outage.
        """
        url = f"{_BASE_URL}/{_FUND_LIST_ENDPOINT}?apikey={self._api_key}"
        try:
            payload = self._request_list(url)
        except ProviderError as exc:
            if "HTTP 401" in str(exc) or "HTTP 403" in str(exc):
                log.info("catalog.fund_list.unavailable", reason="not in free tier")
                return []
            raise
        if not payload:
            log.info("catalog.fund_list.unavailable", reason="empty response")
            return []
        return _parse_instrument_list(payload, instrument_type="fund")

    def fetch_index_list(self) -> list[Instrument]:
        payload = self._get_list(_INDEX_LIST_ENDPOINT)
        return _parse_instrument_list(payload, instrument_type="index")

    def fetch_crypto_list(self) -> list[Instrument]:
        payload = self._get_list(_CRYPTO_LIST_ENDPOINT)
        return _parse_instrument_list(payload, instrument_type="crypto")

    def fetch_exchanges(self) -> list[ExchangeDescriptor]:
        payload = self._get_list(_EXCHANGES_ENDPOINT)
        results: list[ExchangeDescriptor] = []
        for raw_row in payload:
            if not isinstance(raw_row, dict):
                continue
            row: Mapping[str, object] = cast(Mapping[str, object], raw_row)
            code = _first_text(row, "exchange", "code")
            name = _first_text(row, "name", "exchangeFullName") or code
            if not code:
                continue
            results.append(ExchangeDescriptor(code=code, name=name))
        return results

    def fetch_sectors(self) -> list[str]:
        payload = self._get_list(_SECTORS_ENDPOINT)
        return _string_list(payload)

    def fetch_countries(self) -> list[str]:
        payload = self._get_list(_COUNTRIES_ENDPOINT)
        return _string_list(payload)

    def fetch_index_membership(self, index_id: str) -> list[str]:
        endpoint = _INDEX_CONSTITUENT_ENDPOINT_MAP.get(index_id)
        if endpoint is None:
            raise ProviderError(
                self.name,
                f"unbekannter Index '{index_id}' "
                f"(bekannt: {', '.join(sorted(_INDEX_CONSTITUENT_ENDPOINT_MAP))})",
            )
        payload = self._get_list(endpoint)
        tickers: list[str] = []
        for raw_row in payload:
            if not isinstance(raw_row, dict):
                continue
            row: Mapping[str, object] = cast(Mapping[str, object], raw_row)
            symbol = row.get("symbol")
            if isinstance(symbol, str) and symbol.strip():
                tickers.append(symbol.strip().upper())
        return tickers

    def _get_list(self, endpoint: str) -> list[object]:
        if not self._api_key:
            raise ProviderError(self.name, "FINANCIAL_MODELLING_PREP_KEY not set")
        url = f"{_BASE_URL}/{endpoint}?apikey={self._api_key}"
        return self._request_list(url)

    def _request_list(self, url: str) -> list[object]:
        try:
            response = self._session.get(url, timeout=30)
        except requests.RequestException as exc:
            raise ProviderError(self.name, f"network: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitedError(self.name, "HTTP 429")
        if response.status_code != 200:
            raise ProviderError(self.name, f"HTTP {response.status_code}")

        payload = cast(object, response.json())
        if isinstance(payload, dict):
            response_data: Mapping[str, object] = cast(Mapping[str, object], payload)
            error_message = response_data.get("Error Message")
            if isinstance(error_message, str):
                if "LIMIT" in error_message.upper():
                    raise RateLimitedError(self.name, error_message)
                raise ProviderError(self.name, error_message)
            raise ProviderError(self.name, "invalid JSON response")
        if not isinstance(payload, list):
            raise ProviderError(self.name, "invalid JSON response")
        return payload


def _parse_search_results(payload: list[object]) -> list[Instrument]:
    results: list[Instrument] = []
    for raw_row in payload:
        if not isinstance(raw_row, dict):
            continue
        row: Mapping[str, object] = cast(Mapping[str, object], raw_row)
        ticker = row.get("symbol")
        name = row.get("name")
        if not isinstance(ticker, str) or not ticker.strip():
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        exchange = _first_text(row, "exchange", "exchangeFullName")
        currency = _first_text(row, "currency")
        results.append(
            Instrument(
                ticker=ticker.strip().upper(),
                name=name.strip(),
                exchange=exchange or "Unbekannt",
                currency=currency,
            )
        )
    return results


def _first_text(row: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _parse_instrument_list(payload: list[object], *, instrument_type: str) -> list[Instrument]:
    results: list[Instrument] = []
    for raw_row in payload:
        if not isinstance(raw_row, dict):
            continue
        row: Mapping[str, object] = cast(Mapping[str, object], raw_row)
        ticker = row.get("symbol")
        if not isinstance(ticker, str) or not ticker.strip():
            continue
        name = _first_text(row, "name") or ticker.strip()
        exchange = _first_text(row, "exchangeShortName", "exchange")
        exchange_full_name = _first_text(row, "exchangeFullName", "exchange")
        currency = _first_text(row, "currency")
        country = _first_text(row, "country")
        sector = _first_text(row, "sector")
        results.append(
            Instrument(
                ticker=ticker.strip().upper(),
                name=name,
                exchange=exchange or "Unbekannt",
                currency=currency,
                instrument_type=instrument_type,
                country=country,
                sector=sector,
                exchange_full_name=exchange_full_name,
            )
        )
    return results


def _string_list(payload: list[object]) -> list[str]:
    values: list[str] = []
    for raw_row in payload:
        if isinstance(raw_row, str) and raw_row.strip():
            values.append(raw_row.strip())
        elif isinstance(raw_row, dict):
            row: Mapping[str, object] = cast(Mapping[str, object], raw_row)
            text = _first_text(row, "sector", "country", "value", "name")
            if text:
                values.append(text)
    return sorted(dict.fromkeys(values))


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
                adjusted_close=_float(row, "adjClose", fallback_key="close"),
                volume=_int(row, "volume"),
            )
        )
    bars.sort(key=lambda bar: bar.timestamp)
    return bars


def _parse_timestamp(value: str, granularity: Granularity) -> datetime:
    if granularity == Granularity.DAILY:
        return datetime.fromisoformat(f"{value}T16:00:00")
    return datetime.fromisoformat(value)


def _float(row: Mapping[str, object], key: str, *, fallback_key: str | None = None) -> float:
    value = row.get(key)
    if value is None and fallback_key is not None:
        value = row.get(fallback_key)
    if value is None:
        raise ValueError(f"FMP field {key} is not numeric")
    if not isinstance(value, (int, float, str)):
        raise ValueError(f"FMP field {key} is not numeric")
    return float(value)


def _int(row: Mapping[str, object], key: str) -> int:
    value = row[key]
    if not isinstance(value, (int, float, str)):
        raise ValueError(f"FMP field {key} is not numeric")
    return int(float(value))
