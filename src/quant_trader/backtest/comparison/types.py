"""Types and table transformations for strategy comparisons."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from quant_trader.backtest.report import RunSummary


@dataclass(frozen=True)
class ComparisonRow:
    strategy_name: str
    version: str | None = None
    latest_run_id: str | None = None
    total_return_pct: float | None = None
    sharpe: float | None = None
    max_drawdown_pct: float | None = None
    cagr_pct: float | None = None
    n_trades: int | None = None
    exposure_pct: float | None = None


class ComparisonTable:
    @staticmethod
    def build_rows(
        summaries: dict[str, RunSummary | None],
        strategy_versions: dict[str, str] | None = None,
    ) -> list[ComparisonRow]:
        versions = strategy_versions or {}
        return [
            ComparisonRow(
                strategy_name=strategy_name,
                version=versions.get(strategy_name),
                latest_run_id=summary.run_id if summary is not None else None,
                sharpe=summary.sharpe if summary is not None else None,
            )
            for strategy_name, summary in summaries.items()
        ]

    @staticmethod
    def sort_by_sharpe_desc(rows: Sequence[ComparisonRow]) -> list[ComparisonRow]:
        return sorted(
            rows,
            key=lambda row: (
                row.sharpe is None,
                -(row.sharpe if row.sharpe is not None else 0.0),
                row.strategy_name,
            ),
        )
