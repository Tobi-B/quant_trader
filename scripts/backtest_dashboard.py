"""Streamlit-Dashboard: read-only browser view over past backtest reports.

Start: `uv run streamlit run scripts/backtest_dashboard.py`
Requires the `ui` extra: `uv sync --extra ui`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

try:
    import streamlit as st
except ImportError as exc:
    raise SystemExit(
        "streamlit ist nicht installiert. Bitte `uv sync --extra ui` ausfuehren."
    ) from exc

from quant_trader.backtest.report import ReportLoader
from quant_trader.core.config import get_settings
from quant_trader.core.logging import configure_logging, get_logger

log = get_logger(__name__)


def _reports_dir() -> Path:
    settings = get_settings()
    base = Path("./reports")
    log.info("dashboard.start", reports_dir=str(base), data_dir=str(settings.data_dir))
    return base


def _render_equity_curve(report) -> go.Figure:
    fig = go.Figure()
    if not report.equity_curve:
        fig.add_annotation(text="Keine Trades", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
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


def _render_kpi(metrics) -> None:
    if metrics is None:
        st.info("Keine Metriken vorhanden")
        return
    cols = st.columns(4)
    cols[0].metric("Total Return", f"{metrics.total_return_pct:.2f}%")
    cols[1].metric("CAGR", f"{metrics.cagr_pct:.2f}%")
    sharpe_str = "n/a" if metrics.sharpe_ratio is None else f"{metrics.sharpe_ratio:.2f}"
    cols[2].metric("Sharpe", sharpe_str)
    cols[3].metric("Max Drawdown", f"{metrics.max_drawdown_pct:.2f}%")
    cols2 = st.columns(3)
    wr_str = "n/a" if metrics.win_rate_pct is None else f"{metrics.win_rate_pct:.2f}%"
    cols2[0].metric("Win-Rate", wr_str)
    cols2[1].metric("Trades", str(metrics.n_trades))
    cols2[2].metric("Exposure", f"{metrics.exposure_pct:.2f}%")


def _render_trades_table(report) -> None:
    if not report.trades:
        st.info("Keine Trades in diesem Backtest")
        return
    df = pd.DataFrame(
        [
            {
                "Ticker": t.ticker,
                "Entry": t.entry_date.isoformat(),
                "Exit": t.exit_date.isoformat(),
                "Entry Price": t.entry_price,
                "Exit Price": t.exit_price,
                "PnL": t.pnl,
                "PnL %": t.pnl_pct * 100,
            }
            for t in report.trades
        ]
    )
    st.dataframe(df, use_container_width=True)


def main() -> None:
    configure_logging("INFO")
    st.set_page_config(page_title="QuantTrader - Backtest Dashboard", layout="wide")
    st.title("QuantTrader - Backtest Dashboard")

    reports_dir = _reports_dir()
    loader = ReportLoader(reports_dir)
    runs = loader.list_runs()
    if not runs:
        st.info("Noch keine Backtests gelaufen. Bitte zuerst `python -m quant_trader.backtest run ...` aufrufen.")
        return

    st.sidebar.header("Backtest-Auswahl")
    strategy_options = sorted({r.strategy_name for r in runs if r.strategy_name})
    if not strategy_options:
        st.info("Keine laufenden Strategien gefunden.")
        return
    selected_strategy = st.sidebar.selectbox("Strategie", strategy_options)
    filtered = [r for r in runs if r.strategy_name == selected_strategy]
    if not filtered:
        st.info(f"Keine Runs fuer Strategie '{selected_strategy}'.")
        return
    run_options = [r.run_id for r in filtered]
    selected_run_id = st.sidebar.selectbox("Run", run_options)
    report = loader.load_run(selected_run_id)
    st.subheader(f"{report.strategy_name} - {report.run_id}")
    st.caption(
        f"Periode: {report.start} - {report.end}  |  "
        f"Initial Cash: {report.initial_cash:,.2f}  |  "
        f"Final Equity: {report.final_equity:,.2f}  |  "
        f"Fill-Mode: {report.fill_mode}"
    )
    st.plotly_chart(_render_equity_curve(report), use_container_width=True)
    _render_kpi(report.metrics)
    st.subheader("Trades")
    _render_trades_table(report)


if __name__ == "__main__":
    main()
