"""BrokerClient Protocol - the shared broker abstraction."""

from __future__ import annotations

from typing import Protocol

from quant_trader.live.types import Order
from quant_trader.strategies.types import Action


class BrokerClient(Protocol):
    def is_connected(self) -> bool: ...

    def place_order(self, ticker: str, action: Action, qty: int) -> Order: ...

    def get_positions(self) -> dict[str, int]: ...

    def cancel_order(self, client_order_id: str) -> bool: ...


__all__ = ["BrokerClient"]
