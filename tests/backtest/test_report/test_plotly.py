"""Tests for PlotlyExporter: HTML output structure."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from quant_trader.backtest.metrics import Metrics
from quant_trader.backtest.report.plotly_exporter import PlotlyExporter
from quant_trader.backtest.report.types import BacktestReport
from quant_trader.backtest.types import EquitySnapshot, Trade


def _report(
    equity_curve: list[EquitySnapshot] | None = None,
    trades: list[Trade] | None = None,
) -> BacktestReport:
    return BacktestReport(
        run_id="20240102T120000",
        strategy_name="sma_cross",
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
        equity_curve=equity_curve or [],
        trades=trades or [],
    )


def _snapshot(d: date, equity: float) -> EquitySnapshot:
    return EquitySnapshot(
        date=d, equity=equity, cash=0.0, positions={"SPY": 1} if equity > 0 else {}
    )


class TestPlotlyExporter:
    def test_export_creates_file(self, tmp_path: Path) -> None:
        report = _report(
            equity_curve=[
                _snapshot(date(2024, 1, 2), 100_000.0),
                _snapshot(date(2024, 6, 30), 112_000.0),
            ]
        )
        out = tmp_path / "equity.html"
        path = PlotlyExporter().export_equity_curve(report, out)
        assert path == out
        assert out.exists()
        assert out.stat().st_size > 0

    def test_export_html_contains_plotly_marker(self, tmp_path: Path) -> None:
        report = _report(
            equity_curve=[
                _snapshot(date(2024, 1, 2), 100_000.0),
                _snapshot(date(2024, 6, 30), 112_000.0),
            ]
        )
        out = tmp_path / "equity.html"
        PlotlyExporter().export_equity_curve(report, out)
        text = out.read_text(encoding="utf-8")
        assert "plotly" in text.lower()
        assert "Equity" in text

    def test_export_empty_equity_curve(self, tmp_path: Path) -> None:
        report = _report(equity_curve=[])
        out = tmp_path / "empty.html"
        PlotlyExporter().export_equity_curve(report, out)
        text = out.read_text(encoding="utf-8")
        assert "Keine Trades" in text

    def test_export_creates_parent_dirs(self, tmp_path: Path) -> None:
        report = _report(
            equity_curve=[
                _snapshot(date(2024, 1, 2), 100_000.0),
            ]
        )
        out = tmp_path / "subdir" / "nested" / "equity.html"
        PlotlyExporter().export_equity_curve(report, out)
        assert out.exists()
