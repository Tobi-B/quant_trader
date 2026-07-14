"""Backtest engine: simulates a strategy on historical bars and produces trades + equity curve."""

from __future__ import annotations

from quant_trader.backtest.engine import BacktestEngine
from quant_trader.backtest.errors import BacktestConfigError, BacktestError
from quant_trader.backtest.fill import FillSimulator
from quant_trader.backtest.metrics import (
    EquityCurveStats,
    Metrics,
    MetricsCalculator,
    TradeStats,
)
from quant_trader.backtest.portfolio import Portfolio
from quant_trader.backtest.report import (
    BacktestReport,
    ConsoleFormatter,
    JsonExporter,
    PlotlyExporter,
    ReportBuilder,
    ReportLoader,
    ReportPaths,
    RunSummary,
)
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
    "BacktestReport",
    "BacktestResult",
    "ConsoleFormatter",
    "EqualWeightSizer",
    "EquityCurveStats",
    "EquitySnapshot",
    "Fill",
    "FillMode",
    "FillSimulator",
    "JsonExporter",
    "Metrics",
    "MetricsCalculator",
    "PendingFill",
    "PlotlyExporter",
    "Portfolio",
    "PositionSizer",
    "ReportBuilder",
    "ReportLoader",
    "ReportPaths",
    "RunSummary",
    "SizingResult",
    "Trade",
    "TradeStats",
]
