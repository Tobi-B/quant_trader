"""PlotlyExporter: writes interactive equity-curve HTML."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from quant_trader.backtest.report.types import BacktestReport


class PlotlyExporter:
    """Renders a `BacktestReport` equity curve as a self-contained Plotly HTML file."""

    def export_equity_curve(self, report: BacktestReport, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig = self._build_figure(report)
        fig.write_html(str(path), include_plotlyjs="cdn", full_html=True)
        return path

    def _build_figure(self, report: BacktestReport) -> go.Figure:
        fig = go.Figure()
        if not report.equity_curve:
            fig.add_annotation(
                text="Keine Trades",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
            )
            return fig
        dates = [snap.date.isoformat() for snap in report.equity_curve]
        equity = [snap.equity for snap in report.equity_curve]
        positions_hover = [
            ", ".join(f"{t}:{q}" for t, q in snap.positions.items()) or "cash"
            for snap in report.equity_curve
        ]
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=equity,
                mode="lines",
                name="Equity",
                hovertemplate=(
                    "<b>%{x}</b><br>Equity: %{y:,.2f}<br>Positions: %{customdata}<extra></extra>"
                ),
                customdata=positions_hover,
            )
        )
        fig.update_layout(
            title=f"Equity Curve - {report.strategy_name} ({report.run_id})",
            xaxis_title="Datum",
            yaxis_title="Equity (USD)",
            template="plotly_white",
        )
        return fig
