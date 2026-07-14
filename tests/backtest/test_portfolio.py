"""Tests for Portfolio: immutable cash + positions snapshot."""

from __future__ import annotations

import pytest

from quant_trader.backtest.portfolio import Portfolio


def test_default_portfolio_is_empty() -> None:
    p = Portfolio()
    assert p.cash == 0.0
    assert p.positions == {}
    assert p.n_open_positions() == 0


def test_with_cash_returns_new_portfolio() -> None:
    p1 = Portfolio(cash=100.0)
    p2 = p1.with_cash(50.0)
    assert p1.cash == 100.0
    assert p2.cash == 150.0
    assert p1 is not p2


def test_with_cash_negative() -> None:
    p1 = Portfolio(cash=100.0)
    p2 = p1.with_cash(-30.0)
    assert p2.cash == 70.0


def test_with_position_adds_shares() -> None:
    p1 = Portfolio()
    p2 = p1.with_position("SPY", 10)
    assert p2.positions == {"SPY": 10}
    assert p2.n_open_positions() == 1


def test_with_position_closes_position() -> None:
    p1 = Portfolio(positions={"SPY": 10})
    p2 = p1.with_position("SPY", -10)
    assert p2.positions == {}
    assert p2.n_open_positions() == 0


def test_with_position_zero_is_noop() -> None:
    p1 = Portfolio(positions={"SPY": 10})
    p2 = p1.with_position("SPY", 0)
    assert p2.positions == {"SPY": 10}
    assert p2 is p1


def test_with_position_multiple_tickers() -> None:
    p = Portfolio(positions={"SPY": 5, "QQQ": 10})
    assert p.n_open_positions() == 2
    p2 = p.with_position("TLT", 3)
    assert p2.positions == {"SPY": 5, "QQQ": 10, "TLT": 3}


def test_equity_only_cash() -> None:
    p = Portfolio(cash=100.0)
    assert p.equity({}) == pytest.approx(100.0)


def test_equity_with_positions() -> None:
    p = Portfolio(cash=50.0, positions={"SPY": 10, "QQQ": 5})
    equity = p.equity({"SPY": 100.0, "QQQ": 200.0})
    assert equity == pytest.approx(50.0 + 10 * 100.0 + 5 * 200.0)


def test_equity_uses_zero_for_missing_prices() -> None:
    p = Portfolio(cash=100.0, positions={"SPY": 10})
    equity = p.equity({})
    assert equity == pytest.approx(100.0)


def test_position_qty_default_zero() -> None:
    p = Portfolio()
    assert p.position_qty("SPY") == 0


def test_portfolio_is_frozen() -> None:
    p = Portfolio(cash=100.0)
    with pytest.raises((AttributeError, Exception)):
        p.cash = 200.0  # type: ignore[misc]
