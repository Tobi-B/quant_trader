"""Live-trading domain types: Order, OrderStatus, OrderType, Position."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from quant_trader.strategies.types import Action


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass(frozen=True)
class Order:
    id: str
    client_order_id: str
    ticker: str
    action: Action
    qty: int
    type: OrderType
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    filled_qty: int = 0
    avg_fill_price: float | None = None


@dataclass(frozen=True)
class Position:
    ticker: str
    qty: int
    avg_cost: float = 0.0


@dataclass(frozen=True)
class DailySummary:
    """End-of-run summary persisted to the `daily_summaries` table."""

    run_id: str
    strategy_name: str
    total_trades: int
    open_positions_count: int
    total_pnl: float
    duration_seconds: float
    closed_at: str


@dataclass(frozen=True)
class ReconnectConfig:
    """Auto-reconnect tuning parameters for the live loop."""

    initial_delay: float = 1.0
    max_delay: float = 30.0
    max_attempts: int = 10


__all__ = [
    "DailySummary",
    "Order",
    "OrderStatus",
    "OrderType",
    "Position",
    "ReconnectConfig",
]
