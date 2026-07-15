"""Tests for the bulk refresh helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from quant_trader.core.errors import TickerNotFoundError
from quant_trader.core.types import Bar, Granularity
from quant_trader.data.cache import ParquetCache
from quant_trader.data.refresh import (
    RefreshStatus,
    RefreshSummary,
    refresh_all,
    refresh_cached,
    refresh_tickers,
    refresh_universe,
)


class _RecordingProvider:
    def __init__(self, bars: list[Bar] | None = None, exc: Exception | None = None) -> None:
        self.name = "recording"
        self._bars = bars
        self._exc = exc
        self.calls: list[tuple[str, date, date, Any]] = []

    def fetch(self, ticker: str, start: date, end: date, granularity: Any) -> list[Bar]:
        self.calls.append((ticker, start, end, granularity))
        if self._exc is not None:
            raise self._exc
        if self._bars is not None:
            return list(self._bars)
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


class _PerTickerProvider:
    def __init__(self, mapping: dict[str, list[Bar]] | None = None) -> None:
        self.name = "per-ticker"
        self._mapping = mapping or {}
        self.calls: list[str] = []

    def fetch(self, ticker: str, start: date, end: date, granularity: Any) -> list[Bar]:
        self.calls.append(ticker)
        if ticker not in self._mapping:
            raise TickerNotFoundError(ticker)
        return list(self._mapping[ticker])


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


def _seed_cache(cache: ParquetCache, ticker: str, bars: list[Bar]) -> None:
    cache.write(ticker, Granularity.DAILY, bars)


@pytest.fixture
def presets_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg = tmp_path / "presets.yaml"
    cfg.write_text(
        "etfs:\n  description: T\n  tickers: [SPY, AGG]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("UNIVERSE_PRESETS_PATH", str(cfg))
    from quant_trader.core.config import get_settings

    get_settings.cache_clear()
    return cfg


def test_refresh_tickers_returns_summary(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    provider = _RecordingProvider(bars=[_bar(5, 103.0)])

    summary = refresh_tickers(
        ["SPY"],
        cache,
        provider,  # type: ignore[arg-type]
        Granularity.DAILY,
        start=date(2024, 1, 5),
        end=date(2024, 1, 5),
    )

    assert isinstance(summary, RefreshSummary)
    assert summary.total == 1
    assert summary.updated == 1
    assert summary.unchanged == 0
    assert summary.errors == 0
    assert summary.details[0].status == RefreshStatus.UPDATED.value
    assert summary.details[0].bars_added == 1


def test_refresh_tickers_handles_errors_per_ticker(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    provider = _PerTickerProvider({"SPY": [_bar(5, 103.0)]})

    summary = refresh_tickers(
        ["SPY", "ZZZZ"],
        cache,
        provider,  # type: ignore[arg-type]
        Granularity.DAILY,
        start=date(2024, 1, 5),
        end=date(2024, 1, 5),
    )

    assert summary.total == 2
    assert summary.updated == 1
    assert summary.errors == 1
    statuses = {d.ticker: d.status for d in summary.details}
    assert statuses == {"SPY": RefreshStatus.UPDATED.value, "ZZZZ": RefreshStatus.ERROR.value}


def test_refresh_cached_reads_cache_directory(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    _seed_cache(cache, "SPY", [_bar(2, 100.0)])
    _seed_cache(cache, "AGG", [_bar(2, 100.0)])
    provider = _RecordingProvider(bars=[_bar(5, 103.0)])

    summary = refresh_cached(cache, provider, Granularity.DAILY)  # type: ignore[arg-type]

    assert summary.total == 2
    assert summary.errors == 0
    tickers = sorted(d.ticker for d in summary.details)
    assert tickers == ["AGG", "SPY"]


def test_refresh_universe_resolves_tickers(presets_yaml: Path) -> None:
    from quant_trader.core.config import get_settings

    settings = get_settings()
    cache = ParquetCache(settings.data_dir)
    provider = _RecordingProvider(bars=[_bar(5, 103.0)])

    summary = refresh_universe(
        "etfs",
        cache,
        provider,  # type: ignore[arg-type]
        Granularity.DAILY,
        start=date(2024, 1, 5),
        end=date(2024, 1, 5),
    )

    assert summary.total == 2
    assert summary.errors == 0
    assert sorted(d.ticker for d in summary.details) == ["AGG", "SPY"]


def test_refresh_universe_unknown_preset_raises(presets_yaml: Path) -> None:
    from quant_trader.core.config import get_settings
    from quant_trader.universe.presets import PresetNotFoundError

    settings = get_settings()
    cache = ParquetCache(settings.data_dir)
    provider = _RecordingProvider()

    with pytest.raises(PresetNotFoundError):
        refresh_universe("does-not-exist", cache, provider, Granularity.DAILY)  # type: ignore[arg-type]


def test_refresh_summary_aggregates_results(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    _seed_cache(cache, "OLD", [_bar(2, 100.0), _bar(3, 101.0), _bar(4, 102.0), _bar(5, 103.0)])
    provider = _RecordingProvider(bars=[_bar(5, 103.0)])

    summary = refresh_tickers(
        ["OLD", "NEW"],
        cache,
        provider,  # type: ignore[arg-type]
        Granularity.DAILY,
        start=date(2024, 1, 2),
        end=date(2024, 1, 5),
    )

    statuses = {d.ticker: d.status for d in summary.details}
    assert statuses["OLD"] == RefreshStatus.UNCHANGED.value
    assert statuses["NEW"] == RefreshStatus.UPDATED.value
    assert summary.unchanged == 1
    assert summary.updated == 1
    assert summary.errors == 0


def test_refresh_summary_zero_errors_when_all_ok(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    provider = _RecordingProvider(bars=[_bar(5, 103.0)])

    summary = refresh_tickers(
        ["SPY", "AGG"],
        cache,
        provider,  # type: ignore[arg-type]
        Granularity.DAILY,
        start=date(2024, 1, 5),
        end=date(2024, 1, 5),
    )

    assert summary.errors == 0
    assert summary.total == 2


def test_refresh_with_empty_input_returns_zero_summary(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    provider = _RecordingProvider()

    summary = refresh_tickers([], cache, provider, Granularity.DAILY)  # type: ignore[arg-type]

    assert summary.total == 0
    assert summary.updated == 0
    assert summary.unchanged == 0
    assert summary.errors == 0
    assert summary.details == []


def test_refresh_all_deduplicates_overlap(presets_yaml: Path) -> None:
    from quant_trader.core.config import get_settings

    settings = get_settings()
    cache = ParquetCache(settings.data_dir)
    _seed_cache(cache, "SPY", [_bar(2, 100.0)])
    provider = _RecordingProvider(bars=[_bar(5, 103.0)])

    summary = refresh_all(
        cache,
        provider,  # type: ignore[arg-type]
        Granularity.DAILY,
        include_universes=["etfs"],
        start=date(2024, 1, 5),
        end=date(2024, 1, 5),
    )

    tickers = sorted(d.ticker for d in summary.details)
    assert tickers == ["AGG", "SPY"]


def test_refresh_default_window_is_ten_years(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    provider = _RecordingProvider(bars=[_bar(5, 103.0)])

    refresh_tickers(["SPY"], cache, provider, Granularity.DAILY)  # type: ignore[arg-type]

    assert provider.calls, "provider must be called"
    called_start, called_end = provider.calls[0][1], provider.calls[0][2]
    today = date.today()
    assert called_end == today
    assert (today - called_start) >= timedelta(days=365 * 10) - timedelta(days=1)
