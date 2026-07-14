"""ReportLoader: lists and loads BacktestReports from a reports/ directory."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from quant_trader.backtest.metrics import Metrics
from quant_trader.backtest.report.json_exporter import parse_date
from quant_trader.backtest.report.types import BacktestReport, RunSummary
from quant_trader.backtest.types import EquitySnapshot, Trade


class ReportLoader:
    """Reads `result.json` files from `reports/<run_id>/result.json`."""

    def __init__(self, reports_dir: Path) -> None:
        self._dir = reports_dir

    def list_runs(self) -> list[RunSummary]:
        if not self._dir.exists():
            return []
        summaries: list[RunSummary] = []
        for entry in sorted(self._dir.iterdir()):
            if not entry.is_dir():
                continue
            json_path = entry / "result.json"
            if not json_path.exists():
                continue
            try:
                report = self._read_report(json_path, run_id=entry.name)
            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                continue
            summaries.append(
                RunSummary(
                    run_id=report.run_id,
                    strategy_name=report.strategy_name,
                    start=report.start or date(1970, 1, 1),
                    end=report.end or date(1970, 1, 1),
                    final_equity=report.final_equity,
                    sharpe=report.metrics.sharpe_ratio if report.metrics else None,
                )
            )
        return summaries

    def load_run(self, run_id: str) -> BacktestReport:
        json_path = self._dir / run_id / "result.json"
        if not json_path.exists():
            raise FileNotFoundError(f"Kein Report fuer Run '{run_id}': {json_path}")
        return self._read_report(json_path, run_id=run_id)

    @staticmethod
    def _read_report(path: Path, run_id: str) -> BacktestReport:
        with path.open("r", encoding="utf-8") as f:
            raw: dict[str, Any] = json.load(f)
        return BacktestReport(
            run_id=str(raw.get("run_id", run_id)),
            strategy_name=str(raw.get("strategy_name", "")),
            params=dict(raw.get("params", {})),
            start=parse_date(raw.get("start")),
            end=parse_date(raw.get("end")),
            fill_mode=str(raw.get("fill_mode", "next_open")),
            initial_cash=float(raw.get("initial_cash", 0.0)),
            final_equity=float(raw.get("final_equity", 0.0)),
            metrics=_metrics_from_dict(raw.get("metrics")),
            equity_curve=[_snapshot_from_dict(s) for s in raw.get("equity_curve", [])],
            trades=[_trade_from_dict(t) for t in raw.get("trades", [])],
        )


def _metrics_from_dict(raw: dict[str, Any] | None) -> Metrics | None:
    if raw is None:
        return None
    return Metrics(
        total_return_pct=float(raw.get("total_return_pct", 0.0)),
        cagr_pct=float(raw.get("cagr_pct", 0.0)),
        sharpe_ratio=raw.get("sharpe_ratio"),
        max_drawdown_pct=float(raw.get("max_drawdown_pct", 0.0)),
        win_rate_pct=raw.get("win_rate_pct"),
        n_trades=int(raw.get("n_trades", 0)),
        exposure_pct=float(raw.get("exposure_pct", 0.0)),
    )


def _snapshot_from_dict(raw: dict[str, Any]) -> EquitySnapshot:
    return EquitySnapshot(
        date=parse_date(raw.get("date")) or date(1970, 1, 1),
        equity=float(raw.get("equity", 0.0)),
        cash=float(raw.get("cash", 0.0)),
        positions={k: int(v) for k, v in (raw.get("positions") or {}).items()},
    )


def _trade_from_dict(raw: dict[str, Any]) -> Trade:
    return Trade(
        ticker=str(raw.get("ticker", "")),
        entry_date=parse_date(raw.get("entry_date")) or date(1970, 1, 1),
        entry_price=float(raw.get("entry_price", 0.0)),
        exit_date=parse_date(raw.get("exit_date")) or date(1970, 1, 1),
        exit_price=float(raw.get("exit_price", 0.0)),
        pnl=float(raw.get("pnl", 0.0)),
        pnl_pct=float(raw.get("pnl_pct", 0.0)),
    )
