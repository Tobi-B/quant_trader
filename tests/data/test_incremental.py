"""Tests for incremental fetch logic in DataService."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from quant_trader.core.types import Bar, Granularity
from quant_trader.data.cache import ParquetCache
from quant_trader.data.service import compute_missing_ranges


class _RecordingProvider:
    def __init__(self, bars_by_range: dict[tuple[str, str], list[Bar]] | None = None) -> None:
        self.name = "recording"
        self.calls: list[tuple[str, date, date, Granularity]] = []
        self._bars_by_range = bars_by_range or {}

    def fetch(self, ticker: str, start: date, end: date, granularity: Any) -> list[Bar]:
        self.calls.append((ticker, start, end, granularity))
        key = (start.isoformat(), end.isoformat())
        if key in self._bars_by_range:
            return list(self._bars_by_range[key])
        return [
            Bar(
                timestamp=datetime.combine(start, datetime.min.time()).replace(hour=16),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                adjusted_close=100.5,
                volume=1000,
            )
        ]


def _bar(day: int, close: float) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, day, 16, 0),
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        adjusted_close=close,
        volume=1000,
    )


def test_service_uses_cache_when_fully_covered(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0), _bar(3, 101.0), _bar(4, 102.0)])
    provider = _RecordingProvider()

    from quant_trader.data.service import DataService

    service = DataService(cache=cache, provider=provider)
    result = service.get("SPY", date(2024, 1, 2), date(2024, 1, 4), Granularity.DAILY)

    assert result.from_cache is True
    assert result.used_provider == "cache"
    assert provider.calls == []


def test_service_fetches_only_missing_range_right(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0), _bar(3, 101.0)])

    new_bars = [_bar(4, 103.0), _bar(5, 104.0)]
    provider = _RecordingProvider(
        bars_by_range={
            ("2024-01-03", "2024-01-05"): new_bars,
        }
    )

    from quant_trader.data.service import DataService

    service = DataService(cache=cache, provider=provider)
    result = service.get("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)

    assert result.from_cache is False
    assert provider.calls == [("SPY", date(2024, 1, 3), date(2024, 1, 5), Granularity.DAILY)]
    out = cache.read("SPY", Granularity.DAILY, date(2024, 1, 2), date(2024, 1, 5))
    assert [b.close for b in out] == [100.0, 101.0, 103.0, 104.0]


def test_service_fetches_only_missing_range_left(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(4, 103.0), _bar(5, 104.0)])

    new_bars = [_bar(2, 100.0), _bar(3, 101.0)]
    provider = _RecordingProvider(
        bars_by_range={
            ("2024-01-02", "2024-01-04"): new_bars,
        }
    )

    from quant_trader.data.service import DataService

    service = DataService(cache=cache, provider=provider)
    result = service.get("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)

    assert result.from_cache is False
    assert provider.calls == [("SPY", date(2024, 1, 2), date(2024, 1, 4), Granularity.DAILY)]
    out = cache.read("SPY", Granularity.DAILY, date(2024, 1, 2), date(2024, 1, 5))
    assert [b.close for b in out] == [100.0, 101.0, 103.0, 104.0]


def test_service_fetches_full_when_no_cache(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    provider = _RecordingProvider()

    from quant_trader.data.service import DataService

    service = DataService(cache=cache, provider=provider)
    result = service.get("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)

    assert result.from_cache is False
    assert provider.calls == [("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)]
    assert cache.exists("SPY", Granularity.DAILY)


def test_service_skips_provider_when_cache_covers_requested_range(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0), _bar(10, 110.0)])
    provider = _RecordingProvider()

    from quant_trader.data.service import DataService

    service = DataService(cache=cache, provider=provider)
    result = service.get("SPY", date(2024, 1, 3), date(2024, 1, 9), Granularity.DAILY)

    assert result.from_cache is True
    assert provider.calls == []


def test_service_merges_incremental_into_existing_cache(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0), _bar(3, 101.0)])

    custom_bar = _bar(5, 105.0)
    provider = _RecordingProvider(
        bars_by_range={
            ("2024-01-03", "2024-01-05"): [custom_bar],
        }
    )

    from quant_trader.data.service import DataService

    service = DataService(cache=cache, provider=provider)
    result = service.get("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)

    assert result.from_cache is False
    out = cache.read("SPY", Granularity.DAILY, date(2024, 1, 1), date(2024, 1, 31))
    assert len(out) == 3
    closes = sorted(b.close for b in out)
    assert closes == [100.0, 101.0, 105.0]


def test_compute_missing_ranges_no_cache() -> None:
    ranges = compute_missing_ranges(date(2024, 1, 2), date(2024, 1, 10), None, None)
    assert ranges == [(date(2024, 1, 2), date(2024, 1, 10))]


def test_compute_missing_ranges_only_left() -> None:
    ranges = compute_missing_ranges(date(2024, 1, 1), date(2024, 1, 10), date(2024, 1, 5), date(2024, 1, 20))
    assert ranges == [(date(2024, 1, 1), date(2024, 1, 5))]


def test_compute_missing_ranges_only_right() -> None:
    ranges = compute_missing_ranges(date(2024, 1, 2), date(2024, 1, 25), date(2024, 1, 1), date(2024, 1, 10))
    assert ranges == [(date(2024, 1, 10), date(2024, 1, 25))]


def test_compute_missing_ranges_both_sides() -> None:
    ranges = compute_missing_ranges(date(2024, 1, 1), date(2024, 1, 25), date(2024, 1, 5), date(2024, 1, 20))
    assert ranges == [
        (date(2024, 1, 1), date(2024, 1, 5)),
        (date(2024, 1, 20), date(2024, 1, 25)),
    ]


def test_compute_missing_ranges_none_when_covered() -> None:
    ranges = compute_missing_ranges(date(2024, 1, 5), date(2024, 1, 15), date(2024, 1, 1), date(2024, 1, 20))
    assert ranges == []
