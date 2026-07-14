"""Strategy comparison selection and table models."""

from __future__ import annotations

from quant_trader.backtest.comparison.selector import latest_runs_by_strategy
from quant_trader.backtest.comparison.types import ComparisonRow, ComparisonTable

__all__ = ["ComparisonRow", "ComparisonTable", "latest_runs_by_strategy"]
