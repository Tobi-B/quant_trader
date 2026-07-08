"""Tests for DataService."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from quant_trader.core.errors import ProviderError, TickerNotFoundError
from quant_trader.core.types import Bar, Granularity
from quant_trader.data.cache import ParquetCache
from quant_trader.data.service import DataService


class _FakeProvider:
    def __init__(self, name: str, bars: list[Bar] | None = None, exc: Exception | None = None) -> None:
        self.name = name
        self._bars = bars
        self._exc = exc
        self.call_count = 0

    def fetch(self, *args: object, **kwargs: object) -> list[Bar]:
        self.call_count += 1
        if self._exc:
            raise self._exc
        return self._bars or [
            Bar(
                timestamp=datetime(2024, 1, 2, 16, 0),
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


def test_service_cache_hit_skips_provider(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    cache.write("SPY", Granularity.DAILY, [_bar(2, 100.0), _bar(3, 101.0)])
    provider = _FakeProvider("test")

    service = DataService(cache=cache, provider=provider)
    result = service.get("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert result.from_cache is True
    assert result.used_provider == "cache"
    assert provider.call_count == 0
    assert len(result.bars) == 2


def test_service_cache_miss_fetches_and_writes(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    provider = _FakeProvider("test")

    service = DataService(cache=cache, provider=provider)
    result = service.get("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)

    assert result.from_cache is False
    assert result.used_provider == "test"
    assert provider.call_count == 1
    assert cache.exists("SPY", Granularity.DAILY)


def test_service_ticker_not_found_propagates(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    provider = _FakeProvider("test", exc=TickerNotFoundError("ZZZZZ"))

    service = DataService(cache=cache, provider=provider)

    with pytest.raises(TickerNotFoundError):
        service.get("ZZZZZ", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)


def test_service_provider_error_propagates(tmp_path: Path) -> None:
    cache = ParquetCache(tmp_path)
    provider = _FakeProvider("test", exc=ProviderError("test", "boom"))

    service = DataService(cache=cache, provider=provider)

    with pytest.raises(ProviderError):
        service.get("SPY", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)