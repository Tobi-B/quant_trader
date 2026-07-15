"""Bulk refresh of cached market data.

Provides sequential helpers to refresh multiple tickers at once, either
from a free list, all cached tickers, or a universe preset. Errors per
ticker are isolated so one failing ticker does not block the rest.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from quant_trader.core.config import get_settings
from quant_trader.core.logging import get_logger
from quant_trader.core.types import Granularity
from quant_trader.data.cache import ParquetCache
from quant_trader.universe.presets import PresetRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from quant_trader.data.provider import DataProvider


log = get_logger(__name__)


class RefreshStatus(StrEnum):
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    ERROR = "error"


@dataclass(frozen=True)
class RefreshResult:
    ticker: str
    status: str
    bars_added: int
    error_message: str | None
    duration_seconds: float


@dataclass(frozen=True)
class RefreshSummary:
    total: int
    updated: int
    unchanged: int
    errors: int
    duration_seconds: float
    details: list[RefreshResult]


def refresh_tickers(
    tickers: Sequence[str],
    cache: ParquetCache,
    provider: DataProvider,
    granularity: Granularity = Granularity.DAILY,
    *,
    start: date | None = None,
    end: date | None = None,
) -> RefreshSummary:
    """Refresh a list of ``tickers`` via ``cache`` + ``provider``.

    For each ticker the existing cache coverage is checked; only the
    missing date ranges are fetched and merged into the cache.
    """
    started = time.monotonic()
    today = date.today()
    resolved_end = end if end is not None else today
    resolved_start = start if start is not None else today - timedelta(days=365 * 10)

    log.info(
        "data.refresh.start",
        total=len(tickers),
        granularity=granularity.value,
        start=resolved_start.isoformat(),
        end=resolved_end.isoformat(),
    )

    details: list[RefreshResult] = []
    for ticker in tickers:
        details.append(_refresh_one(ticker.upper(), resolved_start, resolved_end, cache, provider, granularity))

    duration = time.monotonic() - started
    summary = _summarise(details, duration)
    log.info(
        "data.refresh.complete",
        total=summary.total,
        updated=summary.updated,
        unchanged=summary.unchanged,
        errors=summary.errors,
        duration_s=round(summary.duration_seconds, 3),
    )
    return summary


def refresh_cached(
    cache: ParquetCache,
    provider: DataProvider,
    granularity: Granularity = Granularity.DAILY,
    *,
    start: date | None = None,
    end: date | None = None,
) -> RefreshSummary:
    """Refresh every ticker already cached for ``granularity``."""
    tickers = cache.list_cached_tickers(granularity)
    return refresh_tickers(tickers, cache, provider, granularity, start=start, end=end)


def refresh_universe(
    universe_name: str,
    cache: ParquetCache,
    provider: DataProvider,
    granularity: Granularity = Granularity.DAILY,
    *,
    start: date | None = None,
    end: date | None = None,
) -> RefreshSummary:
    """Refresh every ticker contained in the named universe preset."""
    repo = PresetRepository(get_settings().universe_presets_path)
    preset = repo.get(universe_name)
    log.info("data.refresh.universe", universe=preset.name, ticker_count=len(preset.tickers))
    return refresh_tickers(preset.tickers, cache, provider, granularity, start=start, end=end)


def refresh_all(
    cache: ParquetCache,
    provider: DataProvider,
    granularity: Granularity = Granularity.DAILY,
    *,
    include_universes: Sequence[str] | None = None,
    start: date | None = None,
    end: date | None = None,
) -> RefreshSummary:
    """Refresh cached tickers plus optionally all tickers of given universes.

    The result is deduplicated: a ticker that appears in both the cache
    listing and one of the universes is refreshed exactly once.
    """
    started = time.monotonic()
    seen: dict[str, None] = {}
    ordered: list[str] = []
    for ticker in cache.list_cached_tickers(granularity):
        if ticker not in seen:
            seen[ticker] = None
            ordered.append(ticker)

    if include_universes:
        repo = PresetRepository(get_settings().universe_presets_path)
        for name in include_universes:
            preset = repo.get(name)
            for ticker in preset.tickers:
                upper = ticker.upper()
                if upper not in seen:
                    seen[upper] = None
                    ordered.append(upper)

    summary = refresh_tickers(ordered, cache, provider, granularity, start=start, end=end)
    duration = time.monotonic() - started
    return RefreshSummary(
        total=summary.total,
        updated=summary.updated,
        unchanged=summary.unchanged,
        errors=summary.errors,
        duration_seconds=duration,
        details=list(summary.details),
    )


def _refresh_one(
    ticker: str,
    start: date,
    end: date,
    cache: ParquetCache,
    provider: DataProvider,
    granularity: Granularity,
) -> RefreshResult:
    started = time.monotonic()
    try:
        covered, cache_min, cache_max = cache.covers_range(ticker, granularity, start, end)
        if covered:
            duration = time.monotonic() - started
            log.info(
                "data.refresh.ticker",
                ticker=ticker,
                status=RefreshStatus.UNCHANGED.value,
                bars_added=0,
                duration_s=round(duration, 3),
            )
            return RefreshResult(
                ticker=ticker,
                status=RefreshStatus.UNCHANGED.value,
                bars_added=0,
                error_message=None,
                duration_seconds=duration,
            )

        from quant_trader.data.service import compute_missing_ranges

        missing = compute_missing_ranges(start, end, cache_min, cache_max)
        all_new_bars: list = []
        for missing_start, missing_end in missing:
            all_new_bars.extend(provider.fetch(ticker, missing_start, missing_end, granularity))

        before_total = 0
        path = cache.path_for(ticker, granularity)
        if path.exists():
            before_total = len(cache.read(ticker, granularity, _MIN_DATE, _MAX_DATE))

        cache.merge_incremental(ticker, granularity, all_new_bars)
        after_total = len(cache.read(ticker, granularity, _MIN_DATE, _MAX_DATE))
        added = max(0, after_total - before_total)

        duration = time.monotonic() - started
        log.info(
            "data.refresh.ticker",
            ticker=ticker,
            status=RefreshStatus.UPDATED.value,
            bars_added=added,
            duration_s=round(duration, 3),
        )
        return RefreshResult(
            ticker=ticker,
            status=RefreshStatus.UPDATED.value,
            bars_added=added,
            error_message=None,
            duration_seconds=duration,
        )
    except Exception as exc:
        duration = time.monotonic() - started
        log.warning(
            "data.refresh.ticker",
            ticker=ticker,
            status=RefreshStatus.ERROR.value,
            error_message=str(exc),
            duration_s=round(duration, 3),
        )
        return RefreshResult(
            ticker=ticker,
            status=RefreshStatus.ERROR.value,
            bars_added=0,
            error_message=str(exc),
            duration_seconds=duration,
        )


def _summarise(details: list[RefreshResult], duration: float) -> RefreshSummary:
    updated = sum(1 for d in details if d.status == RefreshStatus.UPDATED.value)
    unchanged = sum(1 for d in details if d.status == RefreshStatus.UNCHANGED.value)
    errors = sum(1 for d in details if d.status == RefreshStatus.ERROR.value)
    return RefreshSummary(
        total=len(details),
        updated=updated,
        unchanged=unchanged,
        errors=errors,
        duration_seconds=duration,
        details=list(details),
    )


_MIN_DATE = date(1900, 1, 1)
_MAX_DATE = date(2100, 12, 31)
