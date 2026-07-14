"""Tests for ReportLoader."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from quant_trader.backtest.metrics import Metrics
from quant_trader.backtest.report.json_exporter import JsonExporter
from quant_trader.backtest.report.loader import ReportLoader
from quant_trader.backtest.report.types import BacktestReport, RunSummary
from quant_trader.backtest.types import EquitySnapshot


def _write_run(reports_dir: Path, run_id: str, strategy: str = "sma_cross") -> Path:
    run_dir = reports_dir / run_id
    run_dir.mkdir(parents=True)
    report = BacktestReport(
        run_id=run_id,
        strategy_name=strategy,
        params={"fast": 5},
        start=date(2024, 1, 2),
        end=date(2024, 6, 30),
        fill_mode="next_open",
        initial_cash=100_000.0,
        final_equity=112_000.0,
        metrics=Metrics(
            total_return_pct=12.0,
            cagr_pct=5.0,
            sharpe_ratio=1.0,
            max_drawdown_pct=-10.0,
            win_rate_pct=60.0,
            n_trades=2,
            exposure_pct=80.0,
        ),
        equity_curve=[EquitySnapshot(date=date(2024, 1, 2), equity=100_000.0, cash=100_000.0)],
    )
    JsonExporter().export(report, run_dir / "result.json")
    return run_dir


class TestReportLoader:
    def test_list_runs_empty_dir(self, tmp_path: Path) -> None:
        assert ReportLoader(tmp_path).list_runs() == []

    def test_list_runs_nonexistent_dir(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        assert ReportLoader(missing).list_runs() == []

    def test_list_runs_finds_run_dirs(self, tmp_path: Path) -> None:
        _write_run(tmp_path, "run1")
        _write_run(tmp_path, "run2", strategy="momentum")
        summaries = ReportLoader(tmp_path).list_runs()
        assert len(summaries) == 2
        ids = {s.run_id for s in summaries}
        assert ids == {"run1", "run2"}
        assert all(isinstance(s, RunSummary) for s in summaries)

    def test_list_runs_skips_dir_without_json(self, tmp_path: Path) -> None:
        (tmp_path / "no_json").mkdir()
        _write_run(tmp_path, "with_json")
        summaries = ReportLoader(tmp_path).list_runs()
        assert len(summaries) == 1
        assert summaries[0].run_id == "with_json"

    def test_list_runs_summaries_have_expected_fields(self, tmp_path: Path) -> None:
        _write_run(tmp_path, "run1")
        summary = ReportLoader(tmp_path).list_runs()[0]
        assert summary.run_id == "run1"
        assert summary.strategy_name == "sma_cross"
        assert summary.start == date(2024, 1, 2)
        assert summary.end == date(2024, 6, 30)
        assert summary.final_equity == 112_000.0
        assert summary.sharpe == 1.0

    def test_load_run_returns_report(self, tmp_path: Path) -> None:
        _write_run(tmp_path, "run1")
        report = ReportLoader(tmp_path).load_run("run1")
        assert isinstance(report, BacktestReport)
        assert report.run_id == "run1"
        assert report.strategy_name == "sma_cross"
        assert report.metrics is not None
        assert report.metrics.total_return_pct == 12.0

    def test_load_run_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Kein Report"):
            ReportLoader(tmp_path).load_run("nonexistent")
