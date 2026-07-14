"""Tests for the broker factory."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

from quant_trader.core.config import Settings
from quant_trader.live import MockBroker, build_broker


def test_factory_returns_mock_by_default() -> None:
    broker = build_broker(Settings())
    assert isinstance(broker, MockBroker)


def test_factory_returns_mock_when_live_disabled() -> None:
    settings = Settings(live_enabled=False, mock_fill_price=77.0)
    broker = build_broker(settings)
    assert isinstance(broker, MockBroker)
    assert broker._fill_price == 77.0


def test_factory_uses_settings_for_mock_fill_price() -> None:
    settings = Settings(mock_fill_price=123.45)
    broker = build_broker(settings)
    assert isinstance(broker, MockBroker)
    assert broker._fill_price == 123.45


def test_factory_returns_ibkr_when_live_enabled(monkeypatch) -> None:
    sentinel_instance = MagicMock(name="ibkr_instance")
    fake_ibkr_cls = MagicMock(name="IBKRBroker", return_value=sentinel_instance)

    fake_module = ModuleType("quant_trader.live.ibkr")
    fake_module.IBKRBroker = fake_ibkr_cls  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "quant_trader.live.ibkr", fake_module)

    settings = Settings(
        live_enabled=True,
        ibkr_host="10.0.0.1",
        ibkr_port=4002,
        ibkr_client_id=42,
    )

    broker = build_broker(settings)

    fake_ibkr_cls.assert_called_once_with(
        host="10.0.0.1",
        port=4002,
        client_id=42,
    )
    assert broker is sentinel_instance
