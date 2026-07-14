"""IBKR broker integration through ib_insync."""

from __future__ import annotations

import uuid
from datetime import datetime

from quant_trader.core.logging import get_logger
from quant_trader.live.types import Order, OrderStatus, OrderType
from quant_trader.strategies.types import Action

try:
    import ib_insync
except (ImportError, SystemExit) as exc:
    raise SystemExit(
        "ib_insync ist nicht installiert. Bitte `uv sync --extra live` ausfuehren."
    ) from exc

_logger = get_logger("broker.ibkr")


class IBKRBroker:
    """Synchronous BrokerClient adapter for an IBKR TWS connection."""

    name = "ibkr"

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
    ) -> None:
        self._host = host
        self._port = port
        self._client_id = client_id
        self._ib = ib_insync.IB()

    @property
    def ib_client(self) -> object:
        return self._ib

    def connect(self) -> None:
        """Establish connection to TWS. **No credentials in code.**

        The IBKR login happens manually at the TWS prompt (NFR-Sec-2):
        this method calls `ib.connect(host, port, clientId)` without any
        username, password or API-token argument. The Trader must approve
        the API connection in the TWS dialog.
        """
        if not self.is_connected():
            self._ib.connect(self._host, self._port, clientId=self._client_id)

    def disconnect(self) -> None:
        if self.is_connected():
            self._ib.disconnect()

    def is_connected(self) -> bool:
        return bool(self._ib.isConnected())

    def place_order(self, ticker: str, action: Action, qty: int) -> Order:
        if action is Action.HOLD:
            raise ValueError("HOLD cannot be placed as an order")
        if qty <= 0:
            raise ValueError("Order quantity must be positive")
        if not self.is_connected():
            raise RuntimeError("IBKR broker is not connected")
        client_order_id = str(uuid.uuid4())
        created_at = datetime.now()
        contract = ib_insync.Stock(ticker, "SMART", "USD")
        market_order = ib_insync.MarketOrder(
            action.value,
            qty,
            orderRef=client_order_id,
        )
        trade = self._ib.placeOrder(contract, market_order)
        while not trade.isDone():
            self._ib.sleep(0.1)
        updated_at = datetime.now()
        status = self._status_from_ibkr(str(trade.orderStatus.status))
        filled_qty = int(trade.orderStatus.filled)
        avg_fill_price = float(trade.orderStatus.avgFillPrice) if filled_qty > 0 else None
        order = Order(
            id=str(trade.order.orderId),
            client_order_id=client_order_id,
            ticker=ticker,
            action=action,
            qty=qty,
            type=OrderType.MARKET,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            filled_qty=filled_qty,
            avg_fill_price=avg_fill_price,
        )
        _logger.info(
            "broker.order_placed",
            ticker=ticker,
            action=action.value,
            qty=qty,
            client_order_id=client_order_id,
            status=status.value,
        )
        return order

    def get_positions(self) -> dict[str, int]:
        positions: dict[str, int] = {}
        for position in self._ib.positions():
            ticker = str(position.contract.symbol)
            positions[ticker] = positions.get(ticker, 0) + int(position.position)
        return positions

    def cancel_order(self, client_order_id: str) -> bool:
        for trade in self._ib.trades():
            if str(trade.order.orderRef) != client_order_id or trade.isDone():
                continue
            self._ib.cancelOrder(trade.order)
            _logger.info(
                "broker.order_cancelled",
                client_order_id=client_order_id,
            )
            return True
        return False

    @staticmethod
    def _status_from_ibkr(status: str) -> OrderStatus:
        if status == "Filled":
            return OrderStatus.FILLED
        if status in {"Cancelled", "ApiCancelled"}:
            return OrderStatus.CANCELLED
        if status == "Inactive":
            return OrderStatus.REJECTED
        if status in {"PreSubmitted", "Submitted"}:
            return OrderStatus.SUBMITTED
        return OrderStatus.PENDING


__all__ = ["IBKRBroker"]
