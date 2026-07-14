"""Tests for strategy comparison selection and table models."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from quant_trader.backtest.comparison import (
    ComparisonRow,
    ComparisonTable,
    latest_runs_by_strategy,
)
from quant_trader.backtest.metrics import Metrics
from quant_trader.backtest.report import BacktestReport, JsonExporter, ReportLoader, RunSummary


def _write_run(
    reports_dir: Path,
    run_id: str,
    strategy_name: str,
    start: date,
    sharpe: float | None = 1.0,
) -> None:
    report = BacktestReport(
        run_id=run_id,
        strategy_name=strategy_name,
        start=start,
        end=date(2024, 12, 31),
        initial_cash=100_000.0,
        final_equity=110_000.0,
        metrics=Metrics(
            total_return_pct=10.0,
            cagr_pct=8.0,
            sharpe_ratio=sharpe,
            max_drawdown_pct=5.0,
            win_rate_pct=60.0,
            n_trades=4,
            exposure_pct=75.0,
        ),
    )
    JsonExporter().export(report, reports_dir / run_id / "result.json")


def test_latest_runs_with_empty_strategy_names_returns_empty_dict(tmp_path: Path) -> None:
    _write_run(tmp_path, "run-a", "alpha", date(2024, 1, 1))

    assert latest_runs_by_strategy(ReportLoader(tmp_path), []) == {}


def test_latest_runs_without_reports_returns_none_for_all_strategies(tmp_path: Path) -> None:
    result = latest_runs_by_strategy(ReportLoader(tmp_path), ["alpha", "beta", "gamma"])

    assert result == {"alpha": None, "beta": None, "gamma": None}


def test_latest_runs_matches_report_and_keeps_missing_strategy(tmp_path: Path) -> None:
    _write_run(tmp_path, "run-a", "alpha", date(2024, 1, 1))

    result = latest_runs_by_strategy(ReportLoader(tmp_path), ["alpha", "beta"])

    assert result["alpha"] is not None
    assert result["alpha"].run_id == "run-a"
    assert result["beta"] is None


def test_latest_runs_selects_newest_start_per_strategy(tmp_path: Path) -> None:
    _write_run(tmp_path, "alpha-old", "alpha", date(2023, 1, 1))
    _write_run(tmp_path, "alpha-new", "alpha", date(2024, 1, 1))
    _write_run(tmp_path, "beta-new", "beta", date(2024, 2, 1))
    _write_run(tmp_path, "beta-old", "beta", date(2022, 1, 1))

    result = latest_runs_by_strategy(ReportLoader(tmp_path), ["alpha", "beta"])

    assert result["alpha"] is not None
    assert result["alpha"].run_id == "alpha-new"
    assert result["beta"] is not None
    assert result["beta"].run_id == "beta-new"


def test_latest_runs_breaks_start_tie_by_greatest_run_id(tmp_path: Path) -> None:
    _write_run(tmp_path, "run-a", "alpha", date(2024, 1, 1))
    _write_run(tmp_path, "run-b", "alpha", date(2024, 1, 1))

    result = latest_runs_by_strategy(ReportLoader(tmp_path), ["alpha"])

    assert result["alpha"] is not None
    assert result["alpha"].run_id == "run-b"


def test_latest_runs_ignores_unrequested_report_strategy(tmp_path: Path) -> None:
    _write_run(tmp_path, "run-x", "external", date(2024, 1, 1))

    result = latest_runs_by_strategy(ReportLoader(tmp_path), ["alpha"])

    assert result == {"alpha": None}


def test_build_rows_maps_summaries_and_versions() -> None:
    summary = RunSummary(
        run_id="run-a",
        strategy_name="alpha",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        final_equity=110_000.0,
        sharpe=1.25,
    )

    rows = ComparisonTable.build_rows(
        {"alpha": summary, "beta": None},
        strategy_versions={"alpha": "2.0.0", "beta": "1.0.0"},
    )

    assert rows == [
        ComparisonRow(
            strategy_name="alpha",
            version="2.0.0",
            latest_run_id="run-a",
            sharpe=1.25,
        ),
        ComparisonRow(strategy_name="beta", version="1.0.0"),
    ]


def test_sort_by_sharpe_desc_puts_none_last_and_breaks_ties_by_name() -> None:
    rows = [
        ComparisonRow(strategy_name="delta"),
        ComparisonRow(strategy_name="beta", sharpe=2.0),
        ComparisonRow(strategy_name="gamma", sharpe=-1.0),
        ComparisonRow(strategy_name="alpha", sharpe=2.0),
        ComparisonRow(strategy_name="charlie"),
    ]

    result = ComparisonTable.sort_by_sharpe_desc(rows)

    assert [row.strategy_name for row in result] == [
        "alpha",
        "beta",
        "gamma",
        "charlie",
        "delta",
    ]
