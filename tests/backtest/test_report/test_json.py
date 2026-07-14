"""Tests for JsonExporter: roundtrip + schema."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from quant_trader.backtest.metrics import Metrics
from quant_trader.backtest.report.json_exporter import JsonExporter
from quant_trader.backtest.report.types import BacktestReport
from quant_trader.backtest.types import EquitySnapshot, Trade


def _report(include_metrics: bool = True) -> BacktestReport:
    return BacktestReport(
        run_id="20240102T120000",
        strategy_name="sma_cross",
        params={"fast": 5, "slow": 10},
        start=date(2024, 1, 2),
        end=date(2024, 6, 30),
        fill_mode="next_open",
        initial_cash=100_000.0,
        final_equity=112_000.0,
        metrics=(
            Metrics(
                total_return_pct=12.0,
                cagr_pct=5.0,
                sharpe_ratio=1.0,
                max_drawdown_pct=-10.0,
                win_rate_pct=60.0,
                n_trades=2,
                exposure_pct=80.0,
            )
            if include_metrics
            else None
        ),
        equity_curve=[
            EquitySnapshot(date=date(2024, 1, 2), equity=100_000.0, cash=100_000.0),
            EquitySnapshot(
                date=date(2024, 6, 30), equity=112_000.0, cash=0.0, positions={"SPY": 10}
            ),
        ],
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
    )


class TestJsonExporter:
    def test_export_creates_file(self, tmp_path: Path) -> None:
        out = tmp_path / "result.json"
        path = JsonExporter().export(_report(), out)
        assert path == out
        assert out.exists()

    def test_export_schema_top_level_keys(self, tmp_path: Path) -> None:
        out = tmp_path / "result.json"
        JsonExporter().export(_report(), out)
        data = json.loads(out.read_text(encoding="utf-8"))
        expected = {
            "run_id",
            "strategy_name",
            "params",
            "start",
            "end",
            "fill_mode",
            "initial_cash",
            "final_equity",
            "metrics",
            "equity_curve",
            "trades",
        }
        assert set(data.keys()) == expected

    def test_dates_are_iso_strings(self, tmp_path: Path) -> None:
        out = tmp_path / "result.json"
        JsonExporter().export(_report(), out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["start"] == "2024-01-02"
        assert data["end"] == "2024-06-30"
        assert data["equity_curve"][0]["date"] == "2024-01-02"
        assert data["trades"][0]["entry_date"] == "2024-01-10"

    def test_floats_are_numbers(self, tmp_path: Path) -> None:
        out = tmp_path / "result.json"
        JsonExporter().export(_report(), out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data["initial_cash"], (int, float))
        assert isinstance(data["metrics"]["total_return_pct"], (int, float))
        assert isinstance(data["trades"][0]["pnl"], (int, float))

    def test_metrics_null_for_sharpe_when_none(self, tmp_path: Path) -> None:
        report = _report()
        object.__setattr__(report.metrics, "sharpe_ratio", None)  # type: ignore[attr-defined]
        out = tmp_path / "result.json"
        JsonExporter().export(report, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["metrics"]["sharpe_ratio"] is None

    def test_positions_serialized_as_dict(self, tmp_path: Path) -> None:
        out = tmp_path / "result.json"
        JsonExporter().export(_report(), out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["equity_curve"][1]["positions"] == {"SPY": 10}

    def test_roundtrip_via_loader(self, tmp_path: Path) -> None:
        from quant_trader.backtest.report.loader import ReportLoader

        out = tmp_path / "result.json"
        original = _report()
        JsonExporter().export(original, out)
        run_dir = tmp_path / "run1"
        run_dir.mkdir()
        (run_dir / "result.json").write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
        loaded = ReportLoader(tmp_path).load_run("run1")
        assert loaded.run_id == original.run_id
        assert loaded.strategy_name == original.strategy_name
        assert loaded.start == original.start
        assert loaded.end == original.end
        assert loaded.initial_cash == original.initial_cash
        assert loaded.final_equity == original.final_equity
        assert loaded.equity_curve[0].equity == original.equity_curve[0].equity
        assert loaded.trades[0].pnl == original.trades[0].pnl
