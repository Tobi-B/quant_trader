"""JsonExporter: writes a BacktestReport as a stable JSON file."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from quant_trader.backtest.report.types import BacktestReport


class JsonExporter:
    """Serializes a `BacktestReport` to JSON with stable, typed schema.

    Schema (v1):
    - dates: ISO-strings (YYYY-MM-DD)
    - floats: JSON Number
    - lists: JSON arrays
    - None values: JSON null
    """

    def export(self, report: BacktestReport, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._to_dict(report)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=False)
        return path

    @staticmethod
    def _to_dict(report: BacktestReport) -> dict[str, Any]:
        return {
            "run_id": report.run_id,
            "strategy_name": report.strategy_name,
            "params": dict(report.params),
            "start": report.start.isoformat() if report.start else None,
            "end": report.end.isoformat() if report.end else None,
            "fill_mode": report.fill_mode,
            "initial_cash": report.initial_cash,
            "final_equity": report.final_equity,
            "metrics": _metrics_to_dict(report.metrics),
            "equity_curve": [
                {
                    "date": snap.date.isoformat(),
                    "equity": snap.equity,
                    "cash": snap.cash,
                    "positions": dict(snap.positions),
                }
                for snap in report.equity_curve
            ],
            "trades": [
                {
                    "ticker": t.ticker,
                    "entry_date": t.entry_date.isoformat(),
                    "entry_price": t.entry_price,
                    "exit_date": t.exit_date.isoformat(),
                    "exit_price": t.exit_price,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                }
                for t in report.trades
            ],
        }


def _metrics_to_dict(metrics: Any) -> dict[str, Any] | None:
    if metrics is None:
        return None
    return {
        "total_return_pct": metrics.total_return_pct,
        "cagr_pct": metrics.cagr_pct,
        "sharpe_ratio": metrics.sharpe_ratio,
        "max_drawdown_pct": metrics.max_drawdown_pct,
        "win_rate_pct": metrics.win_rate_pct,
        "n_trades": metrics.n_trades,
        "exposure_pct": metrics.exposure_pct,
    }


def parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)
