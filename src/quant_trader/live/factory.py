"""BrokerFactory - assembles the broker client from Settings."""

from __future__ import annotations

from quant_trader.core.config import Settings
from quant_trader.live.mock import MockBroker
from quant_trader.live.protocol import BrokerClient


def build_broker(settings: Settings) -> BrokerClient:
    if settings.live_enabled:
        from quant_trader.live.ibkr import IBKRBroker

        return IBKRBroker(
            host=settings.ibkr_host,
            port=settings.ibkr_port,
            client_id=settings.ibkr_client_id,
        )
    return MockBroker(fill_price=settings.mock_fill_price)


__all__ = ["build_broker"]
