"""Live-trading sub-package: broker interface, mock, order types and IBKR stub."""

from __future__ import annotations

from quant_trader.live.factory import build_broker
from quant_trader.live.mock import MockBroker
from quant_trader.live.protocol import BrokerClient
from quant_trader.live.types import Order, OrderStatus, OrderType, Position

__all__ = [
    "BrokerClient",
    "IBKRBroker",
    "MockBroker",
    "Order",
    "OrderStatus",
    "OrderType",
    "Position",
    "build_broker",
]


def __getattr__(name: str) -> object:
    if name == "IBKRBroker":
        from quant_trader.live.ibkr import IBKRBroker

        return IBKRBroker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
