"""Tests for MockBroker."""

from __future__ import annotations

from datetime import datetime

from quant_trader.live import MockBroker, OrderStatus, OrderType
from quant_trader.strategies import Action


def test_is_connected_returns_true() -> None:
    broker = MockBroker()
    assert broker.is_connected() is True


def test_place_buy_order_executes_synchronously_to_filled() -> None:
    broker = MockBroker(fill_price=42.0)

    order = broker.place_order("SPY", Action.BUY, 10)

    assert order.status is OrderStatus.FILLED
    assert order.filled_qty == 10
    assert order.avg_fill_price == 42.0
    assert order.qty == 10
    assert order.ticker == "SPY"
    assert order.action is Action.BUY
    assert order.type is OrderType.MARKET
    assert order.created_at <= order.updated_at


def test_place_buy_updates_positions() -> None:
    broker = MockBroker()

    broker.place_order("SPY", Action.BUY, 5)

    assert broker.get_positions() == {"SPY": 5}


def test_place_sell_decrements_positions() -> None:
    broker = MockBroker()
    broker.place_order("SPY", Action.BUY, 10)

    broker.place_order("SPY", Action.SELL, 3)

    assert broker.get_positions() == {"SPY": 7}


def test_place_order_with_zero_qty_is_rejected() -> None:
    broker = MockBroker()

    order = broker.place_order("SPY", Action.BUY, 0)

    assert order.status is OrderStatus.REJECTED
    assert order.filled_qty == 0
    assert order.avg_fill_price is None
    assert broker.get_positions() == {}


def test_place_order_with_negative_qty_is_rejected() -> None:
    broker = MockBroker()

    order = broker.place_order("SPY", Action.SELL, -5)

    assert order.status is OrderStatus.REJECTED
    assert broker.get_positions() == {}


def test_get_positions_returns_dict() -> None:
    broker = MockBroker()
    broker.place_order("SPY", Action.BUY, 4)
    broker.place_order("QQQ", Action.BUY, 6)

    positions = broker.get_positions()

    assert positions == {"SPY": 4, "QQQ": 6}


def test_cancel_unknown_order_fails() -> None:
    broker = MockBroker()

    assert broker.cancel_order("nonexistent-uuid") is False


def test_cancel_filled_order_fails() -> None:
    broker = MockBroker()
    order = broker.place_order("SPY", Action.BUY, 1)

    assert broker.cancel_order(order.client_order_id) is False
    assert broker.get_positions() == {"SPY": 1}


def test_cancel_pending_order_succeeds() -> None:
    broker = MockBroker()

    client_order_id = "stuck-pending-uuid"
    from quant_trader.live.types import Order

    pending = Order(
        id=client_order_id,
        client_order_id=client_order_id,
        ticker="SPY",
        action=Action.BUY,
        qty=1,
        type=OrderType.MARKET,
        status=OrderStatus.PENDING,
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        updated_at=datetime(2024, 1, 1, 12, 0, 0),
        filled_qty=0,
        avg_fill_price=None,
    )
    broker._orders[client_order_id] = pending

    assert broker.cancel_order(client_order_id) is True
    assert broker._orders[client_order_id].status is OrderStatus.CANCELLED
    assert broker.get_positions() == {}


def test_client_order_id_is_unique() -> None:
    broker = MockBroker()

    first = broker.place_order("SPY", Action.BUY, 1)
    second = broker.place_order("SPY", Action.BUY, 1)

    assert first.client_order_id != second.client_order_id
    assert first.id == first.client_order_id
    assert second.id == second.client_order_id


def test_order_has_correct_fields() -> None:
    broker = MockBroker(fill_price=99.5)

    order = broker.place_order("QQQ", Action.SELL, 7)

    assert order.id == order.client_order_id
    assert order.client_order_id != ""
    assert order.ticker == "QQQ"
    assert order.action is Action.SELL
    assert order.qty == 7
    assert order.type is OrderType.MARKET
    assert order.status is OrderStatus.FILLED
    assert order.filled_qty == 7
    assert order.avg_fill_price == 99.5
    assert order.created_at is not None
    assert order.updated_at is not None
