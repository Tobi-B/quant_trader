"""Backtest module error hierarchy."""

from __future__ import annotations


class BacktestError(Exception):
    """Base for all backtest-module errors."""


class BacktestConfigError(BacktestError):
    """Backtest configuration is invalid (empty bars, missing sizer, etc.)."""
