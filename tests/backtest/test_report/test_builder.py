"""Tests for ReportBuilder orchestration."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from quant_trader.backtest.report.builder import ReportBuilder
from quant_trader.backtest.types import BacktestResult, EquitySnapshot, FillMode, Trade


def _result() -> BacktestResult:
    return BacktestResult(
        strategy_name="sma_cross",
        params={"fast": 5, "slow": 10},
        start=date(2024, 1, 2),
        end=date(2024, 6, 30),
        fill_mode=FillMode.NEXT_OPEN,
        initial_cash=100_000.0,
        final_equity=112_000.0,
        trades=[
            Trade(
                ticker="SPY",
                entry_date=date(2024, 1, 10),
                entry_price=100.0,
                exit_date=date(2024, 5, 15),
                exit_price=120.0,
                pnl=200.0,
                pnl_pct=0.20,
            )
        ],
        equity_curve=[
            EquitySnapshot(date=date(2024, 1, 2), equity=100_000.0, cash=100_000.0),
            EquitySnapshot(
                date=date(2024, 6, 30), equity=112_000.0, cash=0.0, positions={"SPY": 10}
            ),
        ],
    )


class TestReportBuilder:
    def test_build_creates_files(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "reports"
        paths = ReportBuilder().build(_result(), out_dir, run_id="run1")
        assert paths.equity_html.exists()
        assert paths.result_json.exists()
        assert paths.equity_html.parent.name == "run1"

    def test_build_writes_json_with_metrics(self, tmp_path: Path) -> None:
        import json

        out_dir = tmp_path / "reports"
        ReportBuilder().build(_result(), out_dir, run_id="run1")
        data = json.loads((out_dir / "run1" / "result.json").read_text(encoding="utf-8"))
        assert data["strategy_name"] == "sma_cross"
        assert data["metrics"]["n_trades"] == 1
        assert data["metrics"]["sharpe_ratio"] is None

    def test_build_creates_output_dir(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "new_reports"
        ReportBuilder().build(_result(), out_dir, run_id="run1")
        assert (out_dir / "run1").exists()

    def test_build_returns_paths(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "reports"
        paths = ReportBuilder().build(_result(), out_dir, run_id="abc")
        assert paths.equity_html == out_dir / "abc" / "equity_curve.html"
        assert paths.result_json == out_dir / "abc" / "result.json"

    def test_build_roundtrip(self, tmp_path: Path) -> None:
        from quant_trader.backtest.report.loader import ReportLoader

        out_dir = tmp_path / "reports"
        ReportBuilder().build(_result(), out_dir, run_id="run1")
        summaries = ReportLoader(out_dir).list_runs()
        assert len(summaries) == 1
        assert summaries[0].run_id == "run1"
        loaded = ReportLoader(out_dir).load_run("run1")
        assert loaded.strategy_name == "sma_cross"
        assert len(loaded.trades) == 1
