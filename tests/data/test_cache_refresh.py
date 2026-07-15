"""Tests for ParquetCache merge_incremental and list_cached_tickers."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from quant_trader.core.errors import ProviderError
from quant_trader.core.types import Bar, Granularity
from quant_trader.data.cache import ParquetCache


def _bar(day: int, close: float, volume: int = 1_000_000) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, day, 16, 0, 0),
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        adjusted_close=close,
        volume=volume,
    )


def test_merge_incremental_adds_new_bars(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0), _bar(3, 101.0), _bar(4, 102.0)])

    new_bars = [_bar(5, 103.0), _bar(6, 104.0)]
    cache.merge_incremental("SPY", Granularity.DAILY, new_bars)

    out = cache.read("SPY", Granularity.DAILY, date(2024, 1, 1), date(2024, 1, 31))
    assert [b.close for b in out] == [100.0, 101.0, 102.0, 103.0, 104.0]


def test_merge_incremental_deduplicates_overlap(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0), _bar(3, 101.0), _bar(4, 102.0)])

    overlap = [_bar(3, 999.0), _bar(4, 888.0), _bar(5, 105.0)]
    cache.merge_incremental("SPY", Granularity.DAILY, overlap)

    out = cache.read("SPY", Granularity.DAILY, date(2024, 1, 1), date(2024, 1, 31))
    assert len(out) == 4
    assert [b.close for b in out] == [100.0, 101.0, 102.0, 105.0]


def test_merge_incremental_with_empty_new_bars_returns_existing(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    existing = [_bar(2, 100.0), _bar(3, 101.0)]
    cache.write("SPY", Granularity.DAILY, existing)

    path = cache.merge_incremental("SPY", Granularity.DAILY, [])

    assert path.exists()
    out = cache.read("SPY", Granularity.DAILY, date(2024, 1, 1), date(2024, 1, 31))
    assert [b.close for b in out] == [100.0, 101.0]


def test_merge_incremental_with_empty_new_bars_no_cache_raises(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)

    with pytest.raises(ProviderError):
        cache.merge_incremental("SPY", Granularity.DAILY, [])


def test_merge_incremental_creates_cache_when_missing(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    new_bars = [_bar(2, 100.0), _bar(3, 101.0)]

    cache.merge_incremental("SPY", Granularity.DAILY, new_bars)

    assert cache.exists("SPY", Granularity.DAILY)
    out = cache.read("SPY", Granularity.DAILY, date(2024, 1, 1), date(2024, 1, 31))
    assert [b.close for b in out] == [100.0, 101.0]


def test_merge_incremental_sorts_out_of_order_bars(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0)])

    cache.merge_incremental(
        "SPY",
        Granularity.DAILY,
        [_bar(5, 103.0), _bar(3, 101.0), _bar(4, 102.0)],
    )

    out = cache.read("SPY", Granularity.DAILY, date(2024, 1, 1), date(2024, 1, 31))
    assert [b.timestamp.day for b in out] == [2, 3, 4, 5]


def test_merge_incremental_logs_event(tmp_path: Path) -> None:
    from structlog.testing import capture_logs

    import quant_trader.data.cache as cache_module

    cache_module.log = __import__("structlog").get_logger(cache_module.__name__)
    cache = ParquetCache(tmp_path)

    with capture_logs() as captured:
        cache.merge_incremental("SPY", Granularity.DAILY, [_bar(2, 100.0), _bar(3, 101.0)])

    events = [entry["event"] for entry in captured]
    assert "cache.merge_incremental" in events
