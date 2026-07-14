"""Select the latest report run for each requested strategy."""

from __future__ import annotations

from collections.abc import Sequence

from quant_trader.backtest.report import ReportLoader, RunSummary


def latest_runs_by_strategy(
    loader: ReportLoader,
    strategy_names: Sequence[str],
) -> dict[str, RunSummary | None]:
    selected: dict[str, RunSummary | None] = {name: None for name in strategy_names}
    if not selected:
        return selected

    for summary in loader.list_runs():
        if summary.strategy_name not in selected:
            continue
        current = selected[summary.strategy_name]
        if current is None or (summary.start, summary.run_id) > (current.start, current.run_id):
            selected[summary.strategy_name] = summary
    return selected
