"""Tests for strategy domain types."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from quant_trader.strategies import Action, PortfolioState, Signal, StrategyConfig


def test_action_values() -> None:
    assert Action.BUY == "BUY"
    assert Action.SELL == "SELL"
    assert Action.HOLD == "HOLD"


def test_action_iteration() -> None:
    assert set(Action) == {Action.BUY, Action.SELL, Action.HOLD}


def test_signal_construction() -> None:
    sig = Signal(
        timestamp=datetime(2024, 1, 2, 16, 0),
        ticker="SPY",
        action=Action.BUY,
        reason="sma_cross_up",
    )
    assert sig.ticker == "SPY"
    assert sig.action is Action.BUY
    assert sig.reason == "sma_cross_up"


def test_signal_default_reason() -> None:
    sig = Signal(timestamp=datetime(2024, 1, 2), ticker="SPY", action=Action.BUY)
    assert sig.reason == ""


def test_signal_is_frozen() -> None:
    sig = Signal(timestamp=datetime(2024, 1, 2), ticker="SPY", action=Action.BUY)
    with pytest.raises(FrozenInstanceError):
        sig.ticker = "QQQ"  # type: ignore[misc]


def test_portfolio_state_defaults() -> None:
    state = PortfolioState()
    assert state.cash == 0.0
    assert state.positions == {}


def test_portfolio_state_with_values() -> None:
    state = PortfolioState(cash=10_000.0, positions={"SPY": 50, "QQQ": 25})
    assert state.cash == 10_000.0
    assert state.positions == {"SPY": 50, "QQQ": 25}


def test_portfolio_state_is_frozen() -> None:
    state = PortfolioState()
    with pytest.raises(FrozenInstanceError):
        state.cash = 100.0  # type: ignore[misc]


def test_strategy_config_defaults() -> None:
    cfg = StrategyConfig(strategy_name="sma_cross")
    assert cfg.strategy_name == "sma_cross"
    assert cfg.params == {}


def test_strategy_config_with_params() -> None:
    cfg = StrategyConfig(strategy_name="sma_cross", params={"fast": 20, "slow": 50})
    assert cfg.params == {"fast": 20, "slow": 50}
