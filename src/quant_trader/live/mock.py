"""MockBroker - deterministic broker implementation for tests and CI."""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime
from typing import TypedDict

from quant_trader.core.logging import get_logger
from quant_trader.live.types import Order, OrderStatus, OrderType
from quant_trader.strategies.types import Action

_logger = get_logger("broker.mock")


class _OrderChanges(TypedDict, total=False):
    status: OrderStatus
    filled_qty: int
    avg_fill_price: float
    updated_at: datetime


class MockBroker:
    """Deterministic in-memory broker.

    - `place_order` is synchronous: SUBMITTED -> FILLED in one call.
    - `qty <= 0` results in an Order with `status=REJECTED`.
    - State is held in two dicts: orders by client_order_id, positions by ticker.
    - No randomness, no time-sleep, no network. Suitable for CI without TWS.
    """

    name = "mock"

    def __init__(self, fill_price: float = 100.0) -> None:
        self._fill_price = fill_price
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, int] = {}

    def is_connected(self) -> bool:
        return True

    def place_order(self, ticker: str, action: Action, qty: int) -> Order:
        client_order_id = str(uuid.uuid4())
        now = datetime.now()

        if qty <= 0:
            rejected = Order(
                id=client_order_id,
                client_order_id=client_order_id,
                ticker=ticker,
                action=action,
                qty=qty,
                type=OrderType.MARKET,
                status=OrderStatus.REJECTED,
                created_at=now,
                updated_at=now,
            )
            _logger.warning(
                "broker.order_rejected",
                ticker=ticker,
                action=action.value,
                qty=qty,
                client_order_id=client_order_id,
                reason="qty_must_be_positive",
            )
            self._orders[client_order_id] = rejected
            return rejected

        submitted = Order(
            id=client_order_id,
            client_order_id=client_order_id,
            ticker=ticker,
            action=action,
            qty=qty,
            type=OrderType.MARKET,
            status=OrderStatus.SUBMITTED,
            created_at=now,
            updated_at=now,
        )
        _logger.info(
            "broker.order_placed",
            ticker=ticker,
            action=action.value,
            qty=qty,
            client_order_id=client_order_id,
            fill_price=self._fill_price,
        )

        filled = self._execute(submitted)
        self._orders[client_order_id] = filled

        _logger.info(
            "broker.order_filled",
            ticker=ticker,
            action=action.value,
            qty=qty,
            fill_price=self._fill_price,
            client_order_id=client_order_id,
        )

        return filled

    def get_positions(self) -> dict[str, int]:
        return dict(self._positions)

    def cancel_order(self, client_order_id: str) -> bool:
        order = self._orders.get(client_order_id)
        if order is None:
            return False
        if order.status in (
            OrderStatus.FILLED,
            OrderStatus.REJECTED,
            OrderStatus.CANCELLED,
        ):
            return False
        now = datetime.now()
        self._orders[client_order_id] = self._with_status(
            order, {"status": OrderStatus.CANCELLED, "updated_at": now}
        )
        _logger.info(
            "broker.order_cancelled",
            ticker=order.ticker,
            client_order_id=client_order_id,
        )
        return True

    def _execute(self, order: Order) -> Order:
        now = datetime.now()
        filled = self._with_status(
            order,
            {
                "status": OrderStatus.FILLED,
                "filled_qty": order.qty,
                "avg_fill_price": self._fill_price,
                "updated_at": now,
            },
        )
        delta = filled.qty if filled.action is Action.BUY else -filled.qty
        self._positions[filled.ticker] = self._positions.get(filled.ticker, 0) + delta
        return filled

    @staticmethod
    def _with_status(order: Order, changes: _OrderChanges) -> Order:
        return dataclasses.replace(order, **changes)


__all__ = ["MockBroker"]
