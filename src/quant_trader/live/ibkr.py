"""IBKRBroker - IBKR integration stub (full implementation in Slice 5.2)."""

from __future__ import annotations

from quant_trader.live.types import Order
from quant_trader.strategies.types import Action

try:
    import ib_insync  # noqa: F401
except ImportError as exc:
    raise SystemExit(
        "ib_insync ist nicht installiert. Bitte `uv sync --extra live` ausfuehren."
    ) from exc


class IBKRBroker:
    """IBKR integration skeleton (full implementation arrives in Slice 5.2).

    In Slice 5.1 the broker only stores the connection parameters and
    exposes `NotImplementedError` for every order-management call. The
    real TWS connection, asynchronous event loop and order routing will
    be implemented in Slice 5.2.
    """

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
        self._ib = None

    def is_connected(self) -> bool:
        return False

    def place_order(self, ticker: str, action: Action, qty: int) -> Order:
        raise NotImplementedError(
            "IBKRBroker.place_order ist in Slice 5.1 ein Stub. "
            "Vollstaendige Implementierung in Slice 5.2."
        )

    def get_positions(self) -> dict[str, int]:
        raise NotImplementedError(
            "IBKRBroker.get_positions ist in Slice 5.1 ein Stub. "
            "Vollstaendige Implementierung in Slice 5.2."
        )

    def cancel_order(self, client_order_id: str) -> bool:
        raise NotImplementedError(
            "IBKRBroker.cancel_order ist in Slice 5.1 ein Stub. "
            "Vollstaendige Implementierung in Slice 5.2."
        )


__all__ = ["IBKRBroker"]
