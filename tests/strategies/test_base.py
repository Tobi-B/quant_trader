"""Tests for StrategyBase and MultiTickerStrategyBase ABCs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

import pytest

from quant_trader.core.types import Bar
from quant_trader.strategies import (
    Action,
    MultiTickerStrategyBase,
    PortfolioState,
    Signal,
    StrategyBase,
)


def _bar(close: float = 100.0) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, 2, 16, 0),
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        adjusted_close=close,
        volume=1000,
    )


class _SampleSingleTicker(StrategyBase):
    name: ClassVar[str] = "sample_single"
    version: ClassVar[str] = "0.1.0"
    default_params: ClassVar[dict[str, Any]] = {"threshold": 10, "lookback": 5}

    def warmup_bars(self) -> int:
        return int(self.params["lookback"])

    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
        if bar.close > float(self.params["threshold"]):
            return [Signal(timestamp=bar.timestamp, ticker="SPY", action=Action.BUY)]
        return []


class _SampleMultiTicker(MultiTickerStrategyBase):
    name: ClassVar[str] = "sample_multi"
    default_params: ClassVar[dict[str, Any]] = {"top_n": 2}

    def warmup_bars(self) -> int:
        return 0

    def on_universe_bars(
        self,
        timestamp: datetime,
        bars_by_ticker: dict[str, Bar],
        portfolio: PortfolioState,
    ) -> list[Signal]:
        return []


def test_strategy_base_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        StrategyBase()  # type: ignore[abstract]


def test_concrete_subclass_can_be_instantiated() -> None:
    strategy = _SampleSingleTicker()
    assert strategy.params == {"threshold": 10, "lookback": 5}
    assert strategy.warmup_bars() == 5
    assert strategy.version == "0.1.0"


def test_constructor_params_merge_with_defaults() -> None:
    strategy = _SampleSingleTicker(params={"lookback": 20})
    assert strategy.params == {"threshold": 10, "lookback": 20}


def test_constructor_params_override_defaults() -> None:
    strategy = _SampleSingleTicker(params={"threshold": 50, "lookback": 30})
    assert strategy.params == {"threshold": 50, "lookback": 30}


def test_on_bar_returns_signals_based_on_params() -> None:
    strategy = _SampleSingleTicker(ticker="SPY", params={"threshold": 50})
    bar = _bar(close=60.0)
    signals = strategy.on_bar(bar, PortfolioState())
    assert len(signals) == 1
    assert signals[0].action is Action.BUY
    assert signals[0].ticker == "SPY"


def test_on_bar_returns_empty_when_below_threshold() -> None:
    strategy = _SampleSingleTicker(params={"threshold": 100})
    bar = _bar(close=60.0)
    assert strategy.on_bar(bar, PortfolioState()) == []


def test_multi_ticker_base_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        MultiTickerStrategyBase()  # type: ignore[abstract]


def test_concrete_multi_ticker_subclass_works() -> None:
    strategy = _SampleMultiTicker()
    assert strategy.params == {"top_n": 2}
    assert strategy.warmup_bars() == 0
    signals = strategy.on_universe_bars(datetime(2024, 1, 2), {}, PortfolioState())
    assert signals == []


def test_default_version_is_one_zero() -> None:
    class _Unversioned(StrategyBase):
        name = "unversioned"

        def warmup_bars(self) -> int:
            return 0

        def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
            return []

    assert _Unversioned().version == "1.0.0"
