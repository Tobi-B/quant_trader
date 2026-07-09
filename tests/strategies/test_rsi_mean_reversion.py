"""Tests for RsiMeanReversionStrategy."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from quant_trader.core.types import Bar
from quant_trader.strategies import (
    Action,
    PortfolioState,
    RsiMeanReversionStrategy,
    StrategyError,
)


def _bar(close: float, day_offset: int) -> Bar:
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


def _feed(strategy: RsiMeanReversionStrategy, bars: list[Bar]) -> list:
    sigs: list = []
    for bar in bars:
        sigs.extend(strategy.on_bar(bar, PortfolioState()))
    return sigs


def test_warmup_bars_returns_period_plus_one() -> None:
    strategy = RsiMeanReversionStrategy(ticker="SPY", params={"period": 14})
    assert strategy.warmup_bars() == 15


def test_default_params() -> None:
    strategy = RsiMeanReversionStrategy(ticker="SPY")
    assert strategy.params == {"period": 14, "oversold": 30.0, "overbought": 70.0}


def test_no_signals_during_warmup() -> None:
    strategy = RsiMeanReversionStrategy(ticker="SPY", params={"period": 5})
    bars = _bars_with_closes([100, 100, 100, 100, 100])
    signals = _feed(strategy, bars)
    assert signals == []


def test_no_signals_when_price_constant() -> None:
    strategy = RsiMeanReversionStrategy(ticker="SPY", params={"period": 5})
    bars = _bars_with_closes([100] * 30)
    signals = _feed(strategy, bars)
    assert signals == []


def test_buy_on_oversold_crossing() -> None:
    strategy = RsiMeanReversionStrategy(
        ticker="SPY", params={"period": 5, "oversold": 30.0, "overbought": 70.0}
    )
    bars = _bars_with_closes([100, 100, 100, 100, 100, 100, 100, 100, 90, 90, 90, 90, 90])
    signals = _feed(strategy, bars)
    buy_signals = [s for s in signals if s.action is Action.BUY]
    assert len(buy_signals) == 1
    assert buy_signals[0].reason == "rsi_oversold_cross"
    assert buy_signals[0].ticker == "SPY"


def test_sell_on_overbought_crossing() -> None:
    strategy = RsiMeanReversionStrategy(
        ticker="SPY", params={"period": 5, "oversold": 30.0, "overbought": 70.0}
    )
    bars = _bars_with_closes([100, 100, 100, 100, 100, 100, 100, 90, 100, 110, 120])
    signals = _feed(strategy, bars)
    sell_signals = [s for s in signals if s.action is Action.SELL]
    assert len(sell_signals) == 1
    assert sell_signals[0].reason == "rsi_overbought_cross"
    assert sell_signals[0].ticker == "SPY"


def test_signal_uses_strategy_ticker() -> None:
    strategy = RsiMeanReversionStrategy(
        ticker="QQQ",
        params={"period": 5, "oversold": 30.0, "overbought": 70.0},
    )
    bars = _bars_with_closes([100, 100, 100, 100, 100, 100, 100, 100, 90, 90, 90, 90, 90])
    signals = _feed(strategy, bars)
    assert all(s.ticker == "QQQ" for s in signals)


def test_invalid_period_raises() -> None:
    with pytest.raises(StrategyError, match="period muss >= 1"):
        RsiMeanReversionStrategy(ticker="SPY", params={"period": 0})


def test_invalid_thresholds_oversold_ge_overbought_raises() -> None:
    with pytest.raises(StrategyError, match="muessen in"):
        RsiMeanReversionStrategy(ticker="SPY", params={"oversold": 80.0, "overbought": 70.0})


def test_invalid_thresholds_out_of_range_raises() -> None:
    with pytest.raises(StrategyError, match="muessen in"):
        RsiMeanReversionStrategy(ticker="SPY", params={"oversold": -10.0, "overbought": 50.0})


def test_strategy_loaded_via_loader() -> None:
    from pathlib import Path

    from quant_trader.strategies import StrategyLoader
    from quant_trader.strategies.rsi_mean_reversion import RsiMeanReversionStrategy

    cfg = Path("config/strategies.yaml")
    loader = StrategyLoader(cfg)
    loader.register(RsiMeanReversionStrategy)
    strategy = loader.load("rsi_mean_reversion", ticker="SPY")
    assert isinstance(strategy, RsiMeanReversionStrategy)
    assert strategy.ticker == "SPY"
    assert strategy.params == {"period": 14, "oversold": 30.0, "overbought": 70.0}
