"""ReportBuilder: orchestrates metrics, plotly and json export for a BacktestResult."""

from __future__ import annotations

from pathlib import Path

from quant_trader.backtest.metrics import Metrics, MetricsCalculator
from quant_trader.backtest.report.json_exporter import JsonExporter
from quant_trader.backtest.report.plotly_exporter import PlotlyExporter
from quant_trader.backtest.report.types import BacktestReport, ReportPaths
from quant_trader.backtest.types import BacktestResult


class ReportBuilder:
    """Builds a full report (HTML + JSON) for a `BacktestResult`.

    Writes to `<output_dir>/<run_id>/equity_curve.html` and `result.json`.
    Returns the resulting paths for callers (CLI, dashboard) to log or
    link to.
    """

    def __init__(
        self,
        metrics_calc: MetricsCalculator | None = None,
        plotly_exporter: PlotlyExporter | None = None,
        json_exporter: JsonExporter | None = None,
    ) -> None:
        self._metrics_calc = metrics_calc or MetricsCalculator()
        self._plotly = plotly_exporter or PlotlyExporter()
        self._json = json_exporter or JsonExporter()

    def build(
        self,
        result: BacktestResult,
        output_dir: Path,
        run_id: str,
    ) -> ReportPaths:
        output_dir.mkdir(parents=True, exist_ok=True)
        run_dir = output_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        metrics: Metrics = self._metrics_calc.calculate(result)
        report = BacktestReport(
            run_id=run_id,
            strategy_name=result.strategy_name,
            params=dict(result.params),
            start=result.start,
            end=result.end,
            fill_mode=result.fill_mode.value,
            initial_cash=result.initial_cash,
            final_equity=result.final_equity,
            metrics=metrics,
            equity_curve=list(result.equity_curve),
            trades=list(result.trades),
        )
        equity_path = self._plotly.export_equity_curve(report, run_dir / "equity_curve.html")
        json_path = self._json.export(report, run_dir / "result.json")
        return ReportPaths(equity_html=equity_path, result_json=json_path)
