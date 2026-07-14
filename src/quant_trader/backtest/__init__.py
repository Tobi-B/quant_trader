"""Backtest engine: simulates a strategy on historical bars and produces trades + equity curve."""

from __future__ import annotations

from quant_trader.backtest.engine import BacktestEngine
from quant_trader.backtest.errors import BacktestConfigError, BacktestError
from quant_trader.backtest.fill import FillSimulator
from quant_trader.backtest.portfolio import Portfolio
from quant_trader.backtest.sizer import EqualWeightSizer, PositionSizer, SizingResult
from quant_trader.backtest.types import (
    BacktestConfig,
    BacktestResult,
    EquitySnapshot,
    Fill,
    FillMode,
    PendingFill,
    Trade,
)

__all__ = [
    "BacktestConfig",
    "BacktestConfigError",
    "BacktestEngine",
    "BacktestError",
    "BacktestResult",
    "EqualWeightSizer",
    "EquitySnapshot",
    "Fill",
    "FillMode",
    "FillSimulator",
    "PendingFill",
    "Portfolio",
    "PositionSizer",
    "SizingResult",
    "Trade",
]
