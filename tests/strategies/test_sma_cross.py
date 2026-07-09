"""Tests for SmaCrossStrategy."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from quant_trader.core.types import Bar
from quant_trader.strategies import (
    Action,
    PortfolioState,
    SmaCrossStrategy,
    StrategyError,
)


def _bar(close: float, day_offset: int = 0) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, 2, 16, 0) + timedelta(days=day_offset),
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        adjusted_close=close,
        volume=1000,
    )


def _bars_with_closes(closes: list[float]) -> list[Bar]:
    return [_bar(close=c, day_offset=i) for i, c in enumerate(closes)]


def test_warmup_bars_returns_slow() -> None:
    strategy = SmaCrossStrategy(ticker="SPY", params={"fast": 5, "slow": 20})
    assert strategy.warmup_bars() == 20


def test_default_params() -> None:
    strategy = SmaCrossStrategy(ticker="SPY")
    assert strategy.params == {"fast": 20, "slow": 50}
    assert strategy.warmup_bars() == 50


def test_no_signals_during_warmup() -> None:
    strategy = SmaCrossStrategy(ticker="SPY", params={"fast": 2, "slow": 4})
    bars = _bars_with_closes([10, 10, 10, 10])
    signals: list = []
    for bar in bars:
        signals.extend(strategy.on_bar(bar, PortfolioState()))
    assert signals == []


def test_no_signals_when_price_constant() -> None:
    strategy = SmaCrossStrategy(ticker="SPY", params={"fast": 2, "slow": 4})
    bars = _bars_with_closes([10] * 10)
    signals: list = []
    for bar in bars:
        signals.extend(strategy.on_bar(bar, PortfolioState()))
    assert signals == []


def test_buy_on_up_crossing() -> None:
    strategy = SmaCrossStrategy(ticker="SPY", params={"fast": 2, "slow": 4})
    bars = _bars_with_closes([10, 10, 10, 10, 10, 100, 100, 100])
    signals: list = []
    for bar in bars:
        signals.extend(strategy.on_bar(bar, PortfolioState()))
    buy_signals = [s for s in signals if s.action is Action.BUY]
    assert len(buy_signals) == 1
    assert buy_signals[0].reason == "sma_cross_up"
    assert buy_signals[0].ticker == "SPY"


def test_sell_on_down_crossing() -> None:
    strategy = SmaCrossStrategy(ticker="SPY", params={"fast": 2, "slow": 4})
    bars = _bars_with_closes([100, 100, 100, 100, 100, 10, 10, 10])
    signals: list = []
    for bar in bars:
        signals.extend(strategy.on_bar(bar, PortfolioState()))
    sell_signals = [s for s in signals if s.action is Action.SELL]
    assert len(sell_signals) == 1
    assert sell_signals[0].reason == "sma_cross_down"
    assert sell_signals[0].ticker == "SPY"


def test_signal_uses_strategy_ticker() -> None:
    strategy = SmaCrossStrategy(ticker="QQQ", params={"fast": 2, "slow": 4})
    bars = _bars_with_closes([10, 10, 10, 10, 10, 100])
    signals: list = []
    for bar in bars:
        signals.extend(strategy.on_bar(bar, PortfolioState()))
    assert all(s.ticker == "QQQ" for s in signals)


def test_invalid_params_fast_ge_slow_raises() -> None:
    with pytest.raises(StrategyError, match=r"fast .* muss < slow"):
        SmaCrossStrategy(ticker="SPY", params={"fast": 50, "slow": 20})


def test_invalid_params_fast_too_small_raises() -> None:
    with pytest.raises(StrategyError, match="muessen >= 2"):
        SmaCrossStrategy(ticker="SPY", params={"fast": 1, "slow": 50})


def test_invalid_params_slow_too_small_raises() -> None:
    with pytest.raises(StrategyError, match="muessen >= 2"):
        SmaCrossStrategy(ticker="SPY", params={"fast": 20, "slow": 1})
