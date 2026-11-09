"""Instrument search contracts and service."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Protocol, cast

import requests

from quant_trader.core.errors import DataError, ProviderError, SearchUnavailableError
from quant_trader.core.logging import get_logger
from quant_trader.core.types import Instrument

log = get_logger(__name__)


class InstrumentSearchProvider(Protocol):
    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        exchange: str | None = None,
    ) -> list[Instrument]: ...


class PhantomValidator(Protocol):
    def is_real(self, symbol: str) -> bool: ...


class CompanySearchService:
    """Searches companies and instruments through an injected provider."""

    def __init__(
        self,
        provider: InstrumentSearchProvider,
        phantom_validator: PhantomValidator | None = None,
    ) -> None:
        self._provider = provider
        self._phantom_validator = phantom_validator

    def search(self, query: str, *, limit: int = 20) -> list[Instrument]:
        cleaned = query.strip()
        if not cleaned:
            return []

        bounded_limit = max(1, min(limit, 100))
        log.info("instrument.search.start", query=cleaned, limit=bounded_limit)
        try:
            results = self._provider.search(cleaned, limit=bounded_limit)
        except DataError as exc:
            log.warning(
                "instrument.search.unavailable",
                query=cleaned,
                error_type=type(exc).__name__,
            )
            raise SearchUnavailableError(cleaned, "Suchdienst nicht verfügbar") from exc

        if self._phantom_validator is not None and results:
            filtered = self._filter_phantoms(results, cleaned)
            results = filtered

        log.info("instrument.search.complete", query=cleaned, count=len(results))
        return results

    def _filter_phantoms(self, results: list[Instrument], query: str) -> list[Instrument]:
        validator = self._phantom_validator
        assert validator is not None
        kept: list[Instrument] = []
        dropped = 0
        for instrument in results:
            try:
                if validator.is_real(instrument.ticker):
                    kept.append(instrument)
                else:
                    dropped += 1
                    log.info(
                        "instrument.search.phantom_filtered",
                        query=query,
                        ticker=instrument.ticker,
                        exchange=instrument.exchange,
                    )
            except DataError as exc:
                log.warning(
                    "instrument.search.phantom_validator_error",
                    query=query,
                    ticker=instrument.ticker,
                    error_type=type(exc).__name__,
                    reason=str(exc),
                )
                kept.append(instrument)
        if dropped:
            log.info(
                "instrument.search.phantom_summary",
                query=query,
                dropped=dropped,
                kept=len(kept),
            )
        return kept


class FmpProfilePhantomValidator:
    """Validates symbols by inspecting the FMP profile response."""

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        *,
        base_url: str = "https://financialmodelingprep.com/stable",
    ) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get("FMP_API_KEY", "")
        self._session = session if session is not None else requests.Session()
        self._base_url = base_url

    def is_real(self, symbol: str) -> bool:
        if not self._api_key:
            return True

        url = f"{self._base_url}/profile"
        params = {"symbol": symbol, "apikey": self._api_key}
        try:
            response = self._session.get(url, params=params, timeout=15)
        except requests.RequestException as exc:
            raise ProviderError("fmp", f"network: {exc}") from exc

        if response.status_code == 429:
            raise ProviderError("fmp", "HTTP 429")
        if response.status_code != 200:
            raise ProviderError("fmp", f"HTTP {response.status_code}")

        payload = cast(object, response.json())
        if not isinstance(payload, list) or not payload:
            return False
        first = payload[0]
        if not isinstance(first, dict):
            return False
        row: Mapping[str, object] = cast(Mapping[str, object], first)
        price = row.get("price")
        volume = row.get("volume")
        if price is None:
            return False
        return not (isinstance(volume, (int, float)) and volume <= 0)


__all__ = [
    "CompanySearchService",
    "FmpProfilePhantomValidator",
    "InstrumentSearchProvider",
    "PhantomValidator",
]
