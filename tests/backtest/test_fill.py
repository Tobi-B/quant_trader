"""Tests for FillSimulator: NEXT_OPEN vs SAME_CLOSE behavior."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from quant_trader.backtest.fill import FillSimulator
from quant_trader.backtest.types import FillMode
from quant_trader.core.types import Bar
from quant_trader.strategies.types import Action, Signal


def _bar(open_: float, close: float, day: int = 0) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, 2, 16, 0) + timedelta(days=day),
        open=open_,
        high=max(open_, close) + 1,
        low=min(open_, close) - 1,
        close=close,
        adjusted_close=close,
        volume=1000,
    )


def _bars() -> list[Bar]:
    return [_bar(100.0, 105.0, 0), _bar(110.0, 108.0, 1), _bar(115.0, 120.0, 2)]


def _signal(action: Action, day: int = 0) -> Signal:
    return Signal(
        timestamp=datetime(2024, 1, 2, 16, 0) + timedelta(days=day),
        ticker="SPY",
        action=action,
    )


def test_next_open_uses_next_bar_open() -> None:
    sim = FillSimulator(FillMode.NEXT_OPEN)
    bars = _bars()
    sig = _signal(Action.BUY, day=0)
    pending = sim.schedule(sig, bars, 0)
    assert pending.execute_on is bars[1]
    fill = sim.resolve(pending)
    assert fill.price == 110.0
    assert fill.timestamp == bars[1].timestamp
    assert fill.action == "BUY"


def test_same_close_uses_signal_bar_close() -> None:
    sim = FillSimulator(FillMode.SAME_CLOSE)
    bars = _bars()
    sig = _signal(Action.BUY, day=1)
    pending = sim.schedule(sig, bars, 1)
    assert pending.execute_on is bars[1]
    fill = sim.resolve(pending)
    assert fill.price == 108.0
    assert fill.action == "BUY"


def test_next_open_at_end_of_bars_raises() -> None:
    sim = FillSimulator(FillMode.NEXT_OPEN)
    bars = _bars()
    sig = _signal(Action.BUY, day=2)
    with pytest.raises(ValueError, match="NEXT_OPEN"):
        sim.schedule(sig, bars, 2)
