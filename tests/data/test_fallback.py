"""Tests for FallbackProvider."""

from __future__ import annotations

from datetime import date

import pytest

from quant_trader.core.errors import DataUnavailableError, ProviderError, TickerNotFoundError
from quant_trader.core.types import Bar, Granularity
from quant_trader.data.fallback import FallbackProvider


class _Ok:
    def __init__(self, name: str, bars: list[Bar] | None = None) -> None:
        self.name = name
        self._bars = bars if bars is not None else [
            Bar(timestamp=date(2024, 1, 2), open=1.0, high=2.0, low=0.5, close=1.5, adjusted_close=1.5, volume=100)
        ]

    def fetch(self, *args: object, **kwargs: object) -> list[Bar]:
        return self._bars


class _Fail:
    def __init__(self, name: str, exc: Exception) -> None:
        self.name = name
        self._exc = exc

    def fetch(self, *args: object, **kwargs: object) -> list[Bar]:
        raise self._exc


def test_fallback_returns_primary_when_ok() -> None:
    primary = _Ok("p")
    fallback = FallbackProvider(primary, [])

    bars = fallback.fetch("X", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert bars == primary._bars


def test_fallback_tries_secondary_when_primary_fails() -> None:
    primary = _Fail("p", ProviderError("p", "boom"))
    secondary = _Ok("s")

    chain = FallbackProvider(primary, [secondary])
    bars = chain.fetch("X", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert bars == secondary._bars


def test_fallback_tries_tertiary_when_secondary_fails() -> None:
    primary = _Fail("p", ProviderError("p", "boom"))
    secondary = _Fail("s", ProviderError("s", "boom"))
    tertiary = _Ok("t")

    chain = FallbackProvider(primary, [secondary, tertiary])
    bars = chain.fetch("X", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert bars == tertiary._bars


def test_fallback_raises_data_unavailable_when_all_fail() -> None:
    primary = _Fail("p", ProviderError("p", "first"))
    secondary = _Fail("s", ProviderError("s", "second"))

    chain = FallbackProvider(primary, [secondary])
    with pytest.raises(DataUnavailableError) as exc:
        chain.fetch("X", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)

    assert exc.value.ticker == "X"
    assert len(exc.value.reasons) == 2


def test_fallback_ticker_not_found_is_fail_fast() -> None:
    primary = _Fail("p", TickerNotFoundError("XYZ"))
    secondary = _Ok("s")

    chain = FallbackProvider(primary, [secondary])
    with pytest.raises(TickerNotFoundError) as exc:
        chain.fetch("XYZ", date(2024, 1, 2), date(2024, 1, 5), Granularity.DAILY)
    assert exc.value.ticker == "XYZ"


def test_fallback_chain_property_includes_primary() -> None:
    primary = _Ok("p")
    secondary = _Ok("s")
    chain = FallbackProvider(primary, [secondary])
    assert chain._chain == [primary, secondary]


def test_fallback_name_is_fallback() -> None:
    chain = FallbackProvider(_Ok("p"), [])
    assert chain.name == "fallback"