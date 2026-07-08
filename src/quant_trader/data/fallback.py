"""FallbackProvider - decorator that tries a primary, then a list of fallbacks."""

from __future__ import annotations

from datetime import date

from quant_trader.core.errors import (
    DataUnavailable,
    ProviderError,
    TickerNotFound,
)
from quant_trader.core.logging import get_logger
from quant_trader.core.types import Bar, Granularity

log = get_logger(__name__)


class FallbackProvider:
    def __init__(self, primary: object, fallbacks: list[object]) -> None:
        self._primary = primary
        self._fallbacks = fallbacks
        self._chain: list[object] = [primary, *fallbacks]

    @property
    def name(self) -> str:
        return "fallback"

    def fetch(
        self,
        ticker: str,
        start: date,
        end: date,
        granularity: Granularity,
    ) -> list[Bar]:
        reasons: list[str] = []
        for provider in self._chain:
            provider_name = getattr(provider, "name", type(provider).__name__)
            try:
                return provider.fetch(ticker, start, end, granularity)
            except TickerNotFound:
                raise
            except ProviderError as exc:
                log.warning(
                    "provider.fallback",
                    provider=provider_name,
                    ticker=ticker,
                    reason=str(exc),
                )
                reasons.append(str(exc))
        raise DataUnavailable(ticker, reasons)