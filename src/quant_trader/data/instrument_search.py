"""Instrument search contracts and service."""

from __future__ import annotations

from typing import Protocol

from quant_trader.core.errors import DataError, SearchUnavailableError
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


class CompanySearchService:
    """Searches companies and instruments through an injected provider."""

    def __init__(self, provider: InstrumentSearchProvider) -> None:
        self._provider = provider

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
        log.info("instrument.search.complete", query=cleaned, count=len(results))
        return results


__all__ = ["CompanySearchService", "InstrumentSearchProvider"]
