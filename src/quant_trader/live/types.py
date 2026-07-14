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


__all__ = ["Order", "OrderStatus", "OrderType", "Position"]
