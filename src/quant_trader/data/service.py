"""DataService - orchestrates cache check + provider fetch + cache write."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from quant_trader.core.logging import get_logger
from quant_trader.core.types import Bar, Granularity
from quant_trader.data.cache import ParquetCache

log = get_logger(__name__)


@dataclass(frozen=True)
class FetchResult:
    ticker: str
    bars: list[Bar]
    from_cache: bool
    used_provider: str


class DataService:
    def __init__(self, cache: ParquetCache, provider: object) -> None:
        self._cache = cache
        self._provider = provider

    def get(
        self,
        ticker: str,
        start: date,
        end: date,
        granularity: Granularity,
    ) -> FetchResult:
        if granularity != Granularity.DAILY:
            log.warning(
                "intraday.api_quota_high",
                ticker=ticker,
                granularity=granularity.value,
                hint="Intraday-Intervalle verbrauchen mehr API-Quota als Tagesdaten.",
            )

        if self._cache.covers(ticker, granularity, start, end):
            log.info("cache.hit", ticker=ticker, granularity=granularity.value)
            bars = self._cache.read(ticker, granularity, start, end)
            return FetchResult(
                ticker=ticker,
                bars=bars,
                from_cache=True,
                used_provider="cache",
            )

        provider_name = getattr(self._provider, "name", type(self._provider).__name__)
        log.info("provider.fetch", ticker=ticker, provider=provider_name)
        bars = self._provider.fetch(ticker, start, end, granularity)
        self._cache.write(ticker, granularity, bars)
        log.info("cache.written", ticker=ticker, count=len(bars))
        return FetchResult(
            ticker=ticker,
            bars=bars,
            from_cache=False,
            used_provider=provider_name,
        )