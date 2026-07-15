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

        covered, cache_min, cache_max = self._cache.covers_range(ticker, granularity, start, end)
        if covered:
            log.info("cache.hit", ticker=ticker, granularity=granularity.value)
            bars = self._cache.read(ticker, granularity, start, end)
            return FetchResult(
                ticker=ticker,
                bars=bars,
                from_cache=True,
                used_provider="cache",
            )

        missing_ranges = compute_missing_ranges(start, end, cache_min, cache_max)
        if not missing_ranges:
            log.info("cache.hit", ticker=ticker, granularity=granularity.value)
            bars = self._cache.read(ticker, granularity, start, end)
            return FetchResult(
                ticker=ticker,
                bars=bars,
                from_cache=True,
                used_provider="cache",
            )

        provider_name = getattr(self._provider, "name", type(self._provider).__name__)
        log.info(
            "data.service.incremental_fetch",
            ticker=ticker,
            granularity=granularity.value,
            provider=provider_name,
            missing_ranges=[(s.isoformat(), e.isoformat()) for s, e in missing_ranges],
        )

        all_new_bars: list[Bar] = []
        for missing_start, missing_end in missing_ranges:
            all_new_bars.extend(self._provider.fetch(ticker, missing_start, missing_end, granularity))

        self._cache.merge_incremental(ticker, granularity, all_new_bars)
        log.info("cache.written", ticker=ticker, count=len(all_new_bars))

        bars = self._cache.read(ticker, granularity, start, end)
        return FetchResult(
            ticker=ticker,
            bars=bars,
            from_cache=False,
            used_provider=provider_name,
        )


def compute_missing_ranges(
    start: date,
    end: date,
    cache_min: date | None,
    cache_max: date | None,
) -> list[tuple[date, date]]:
    """Return date ranges that need to be fetched from the provider.

    Both endpoints are inclusive: ``merge_incremental`` deduplicates
    overlap with the existing cache. Exposed for reuse by the bulk
    refresh helpers.
    """
    if cache_min is None or cache_max is None:
        return [(start, end)]
    ranges: list[tuple[date, date]] = []
    if start < cache_min:
        ranges.append((start, cache_min))
    if end > cache_max:
        ranges.append((cache_max, end))
    return ranges
