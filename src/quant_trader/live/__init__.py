"""Live-trading package: brokers, realtime bars, journal and execution loop."""

from __future__ import annotations

from quant_trader.live.bars import IBKRBarSource, MockBarSource, RealtimeBarSource
from quant_trader.live.factory import build_broker
from quant_trader.live.journal import TradeJournal, TradeRow
from quant_trader.live.loop import LiveLoop, LiveLoopSummary
from quant_trader.live.mock import MockBroker
from quant_trader.live.protocol import BrokerClient
from quant_trader.live.summary import DailySummaryFormatter
from quant_trader.live.types import (
    DailySummary,
    Order,
    OrderStatus,
    OrderType,
    Position,
    ReconnectConfig,
)

__all__ = [
    "BrokerClient",
    "DailySummary",
    "DailySummaryFormatter",
    "IBKRBarSource",
    "IBKRBroker",
    "LiveLoop",
    "LiveLoopSummary",
    "MockBarSource",
    "MockBroker",
    "Order",
    "OrderStatus",
    "OrderType",
    "Position",
    "RealtimeBarSource",
    "ReconnectConfig",
    "TradeJournal",
    "TradeRow",
    "build_broker",
]


def __getattr__(name: str) -> object:
    if name == "IBKRBroker":
        from quant_trader.live.ibkr import IBKRBroker

        return IBKRBroker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
