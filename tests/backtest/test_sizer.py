"""Tests for EqualWeightSizer and SizingResult."""

from __future__ import annotations

import pytest

from quant_trader.backtest.sizer import EqualWeightSizer


def test_equal_weight_first_position_uses_full_cash() -> None:
    sizer = EqualWeightSizer()
    result = sizer.allocate(price=100.0, available_cash=100_000.0, n_open_positions=0)
    assert result.skipped is False
    assert result.qty == 1000
    assert result.allocated_cash == pytest.approx(100_000.0, abs=0.01)


def test_equal_weight_third_of_three_splits_three_ways() -> None:
    sizer = EqualWeightSizer()
    result = sizer.allocate(price=100.0, available_cash=100_000.0, n_open_positions=2)
    assert result.skipped is False
    assert result.qty == 333
    assert result.allocated_cash == pytest.approx(33_300.0, abs=0.01)


def test_equal_weight_with_one_existing_position() -> None:
    sizer = EqualWeightSizer()
    result = sizer.allocate(price=100.0, available_cash=50_000.0, n_open_positions=1)
    assert result.skipped is False
    assert result.qty == 250
    assert result.allocated_cash == pytest.approx(25_000.0, abs=0.01)


def test_equal_weight_zero_cash_skips() -> None:
    sizer = EqualWeightSizer()
    result = sizer.allocate(price=100.0, available_cash=0.0, n_open_positions=0)
    assert result.skipped is True
    assert result.qty == 0
    assert result.allocated_cash == 0.0


def test_equal_weight_negative_cash_skips() -> None:
    sizer = EqualWeightSizer()
    result = sizer.allocate(price=100.0, available_cash=-10.0, n_open_positions=0)
    assert result.skipped is True
    assert result.qty == 0


def test_equal_weight_too_expensive_skips() -> None:
    sizer = EqualWeightSizer()
    result = sizer.allocate(price=10_000.0, available_cash=1_000.0, n_open_positions=0)
    assert result.skipped is True
    assert result.qty == 0


def test_equal_weight_zero_price_skips() -> None:
    sizer = EqualWeightSizer()
    result = sizer.allocate(price=0.0, available_cash=1_000.0, n_open_positions=0)
    assert result.skipped is True


def test_equal_weight_negative_price_skips() -> None:
    sizer = EqualWeightSizer()
    result = sizer.allocate(price=-10.0, available_cash=1_000.0, n_open_positions=0)
    assert result.skipped is True


def test_equal_weight_single_position_no_other() -> None:
    sizer = EqualWeightSizer()
    result = sizer.allocate(price=50.0, available_cash=10_000.0, n_open_positions=0)
    assert result.skipped is False
    assert result.qty == 200
    assert result.allocated_cash == pytest.approx(10_000.0, abs=0.01)
