"""Report domain types: ReportPaths, RunSummary, BacktestReport."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from quant_trader.backtest.metrics import Metrics
from quant_trader.backtest.types import EquitySnapshot, Trade


@dataclass(frozen=True)
class ReportPaths:
    equity_html: Path
    result_json: Path


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    strategy_name: str
    start: date
    end: date
    final_equity: float
    sharpe: float | None


@dataclass(frozen=True)
class BacktestReport:
    run_id: str
    strategy_name: str
    params: dict[str, Any] = field(default_factory=dict)
    start: date | None = None
    end: date | None = None
    fill_mode: str = "next_open"
    initial_cash: float = 0.0
    final_equity: float = 0.0
    metrics: Metrics | None = None
    equity_curve: list[EquitySnapshot] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
