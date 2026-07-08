"""Tests for ParquetCache."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from quant_trader.core.errors import ProviderError
from quant_trader.core.types import Bar, Granularity
from quant_trader.data.cache import ParquetCache


def _bar(day: int, close: float) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, day, 16, 0, 0),
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        adjusted_close=close,
        volume=1_000_000,
    )


def test_cache_path_for(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    assert cache.path_for("SPY", Granularity.DAILY) == tmp_path / "raw" / "daily" / "SPY.parquet"
    assert cache.path_for("AAPL", Granularity.INTRADAY_60M) == tmp_path / "raw" / "60m" / "AAPL.parquet"


def test_cache_exists_false_initially(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    assert cache.exists("SPY", Granularity.DAILY) is False


def test_cache_write_then_read_roundtrip(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    bars = [_bar(2, 100.0), _bar(3, 101.5), _bar(4, 102.0)]

    cache.write("SPY", Granularity.DAILY, bars)
    out = cache.read("SPY", Granularity.DAILY, date(2024, 1, 1), date(2024, 1, 31))

    assert len(out) == 3
    assert out[1].close == 101.5
    assert out[2].volume == 1_000_000


def test_cache_write_creates_parent_dirs(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path / "deep" / "nested")
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0)])
    assert cache.exists("SPY", Granularity.DAILY)


def test_cache_write_empty_raises(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)

    with pytest.raises(ProviderError):
        cache.write("SPY", Granularity.DAILY, [])


def test_cache_covers_returns_true_when_range_inside_cache(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0), _bar(10, 110.0)])

    assert cache.covers("SPY", Granularity.DAILY, date(2024, 1, 3), date(2024, 1, 9)) is True


def test_cache_covers_returns_false_when_range_outside(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0), _bar(10, 110.0)])

    assert cache.covers("SPY", Granularity.DAILY, date(2024, 1, 1), date(2024, 12, 31)) is False


def test_cache_covers_returns_false_when_missing(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    assert cache.covers("SPY", Granularity.DAILY, date(2024, 1, 1), date(2024, 1, 31)) is False


def test_cache_read_returns_only_bars_in_range(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0), _bar(3, 101.0), _bar(4, 102.0)])

    out = cache.read("SPY", Granularity.DAILY, date(2024, 1, 3), date(2024, 1, 3))
    assert len(out) == 1
    assert out[0].close == 101.0


def test_cache_paths_are_separated_per_granularity(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0)])

    assert (tmp_path / "raw" / "daily" / "SPY.parquet").exists()
    assert not (tmp_path / "raw" / "60m" / "SPY.parquet").exists()
    assert cache.exists("SPY", Granularity.DAILY) is True
    assert cache.exists("SPY", Granularity.INTRADAY_60M) is False
    assert cache.exists("SPY", Granularity.INTRADAY_15M) is False


def test_cache_intraday_writes_to_own_directory(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("AAPL", Granularity.INTRADAY_60M, [_bar(2, 195.0)])

    assert (tmp_path / "raw" / "60m" / "AAPL.parquet").exists()
    assert not (tmp_path / "raw" / "daily" / "AAPL.parquet").exists()


def test_cache_intraday_covers_uses_correct_file(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("AAPL", Granularity.INTRADAY_60M, [_bar(2, 195.0), _bar(10, 200.0)])

    assert cache.covers("AAPL", Granularity.INTRADAY_60M, date(2024, 1, 3), date(2024, 1, 9)) is True
    assert cache.covers("AAPL", Granularity.INTRADAY_60M, date(2024, 1, 1), date(2024, 1, 31)) is False