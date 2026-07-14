"""Backtest domain types: FillMode, BacktestConfig, Fill, Trade, EquitySnapshot, BacktestResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from quant_trader.core.types import Bar
from quant_trader.strategies.types import Signal


class FillMode(StrEnum):
    NEXT_OPEN = "next_open"
    SAME_CLOSE = "same_close"


@dataclass(frozen=True)
class Fill:
    ticker: str
    timestamp: datetime
    price: float
    qty: int
    action: str
    fee: float = 0.0


@dataclass(frozen=True)
class PendingFill:
    signal: Signal
    execute_on: Bar


@dataclass(frozen=True)
class Trade:
    ticker: str
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    pnl: float
    pnl_pct: float


@dataclass(frozen=True)
class EquitySnapshot:
    date: date
    equity: float
    cash: float
    positions: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float
    fill_mode: FillMode
    sizer: object
    start: date | None = None
    end: date | None = None
    commission_per_trade: float = 0.0
    commission_per_share: float = 0.0
    slippage_pct: float = 0.0
    stop_loss_pct: float | None = None


@dataclass(frozen=True)
class BacktestResult:
    strategy_name: str
    params: dict[str, object]
    start: date
    end: date
    fill_mode: FillMode
    initial_cash: float
    final_equity: float
    trades: list[Trade]
    equity_curve: list[EquitySnapshot]
