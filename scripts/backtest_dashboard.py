"""Streamlit-Dashboard: interactive browser view over the backtest system.

Start: `uv run streamlit run scripts/backtest_dashboard.py`
Requires the `ui` extra: `uv sync --extra ui`.

Tabs:
- "Run-Form" (US-P3.9): pick strategy + ticker/universe + date range, click
  "Backtest starten", see the result (KPIs + equity curve + trades) right
  under the form in the same tab.
- "Read-Mode" (US-P3.7): browse past backtest reports from `reports/`.
- "Vergleich" (US-P3.10): compare the latest report for every registered strategy.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

try:
    import streamlit as st
except ImportError as exc:
    raise SystemExit(
        "streamlit ist nicht installiert. Bitte `uv sync --extra ui` ausfuehren."
    ) from exc

from quant_trader.backtest.comparison import (
    ComparisonRow,
    ComparisonTable,
    latest_runs_by_strategy,
)
from quant_trader.backtest.dashboard_runner import DashboardRunner
from quant_trader.backtest.errors import (
    BacktestError,
    CacheMissingError,
    InvalidParamsError,
    UnknownStrategyError,
)
from quant_trader.backtest.metrics import Metrics, MetricsCalculator
from quant_trader.backtest.orchestrator import BacktestOrchestrator
from quant_trader.backtest.report import BacktestReport, ReportLoader
from quant_trader.backtest.types import BacktestResult
from quant_trader.core.config import get_settings
from quant_trader.core.logging import configure_logging, get_logger
from quant_trader.data.cache import ParquetCache
from quant_trader.strategies import default_loader
from quant_trader.universe.presets import PresetRepository

log = get_logger(__name__)

_REPORTS_DIR = Path("./reports")
_CUSTOM_TICKER_OPTION = "(Custom-Ticker)"
_RUN_FORM_TAB = "Run-Form"
_READ_MODE_TAB = "Read-Mode"
_COMPARISON_TAB = "Vergleich"


def _reports_dir() -> Path:
    settings = get_settings()
    log.info("dashboard.start", reports_dir=str(_REPORTS_DIR), data_dir=str(settings.data_dir))
    return _REPORTS_DIR


@st.cache_resource(show_spinner=False)
def _build_services() -> tuple[
    ReportLoader,
    DashboardRunner,
    list[str],
    list[str],
]:
    """Build the long-lived services once per Streamlit session."""
    loader = default_loader()
    presets = PresetRepository(get_settings().universe_presets_path)
    orchestrator = BacktestOrchestrator(
        cache=ParquetCache(get_settings().data_dir),
        loader=loader,
        reports_dir=_REPORTS_DIR,
    )
    runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)
    strategy_names = loader.registered_names()
    preset_names = presets.names()
    return ReportLoader(_REPORTS_DIR), runner, strategy_names, preset_names


def _render_equity_curve(report: BacktestReport) -> go.Figure:
    fig = go.Figure()
    if not report.equity_curve:
        fig.add_annotation(
            text="Keine Trades", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False
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


def _render_comparison_equity_curve(report: BacktestReport) -> go.Figure:
    fig = _render_equity_curve(report)
    fig.update_layout(
        title=f"{report.strategy_name} - {report.run_id}",
        height=320,
        showlegend=False,
    )
    return fig


def _render_kpi(metrics: Metrics | None) -> None:
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


def _render_trades_table(report: BacktestReport) -> None:
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


def _render_run_form(
    runner: DashboardRunner, strategy_names: list[str], preset_names: list[str]
) -> None:
    st.subheader("Neuen Backtest starten")
    if not strategy_names:
        st.info("Keine Strategien registriert")
        return

    prefill_strategy = st.session_state.pop("prefill_strategy", None)
    strategy_index = (
        strategy_names.index(prefill_strategy)
        if isinstance(prefill_strategy, str) and prefill_strategy in strategy_names
        else 0
    )
    with st.sidebar.form(key="run_form"):
        st.header("Backtest-Konfiguration")
        strategy = st.selectbox("Strategie", strategy_names, index=strategy_index)
        universe_options = [_CUSTOM_TICKER_OPTION, *preset_names]
        universe_choice = st.selectbox("Universe-Preset", universe_options)
        ticker = ""
        if universe_choice == _CUSTOM_TICKER_OPTION:
            ticker = st.text_input("Ticker", value="", placeholder="z.B. SPY")
        today = date.today()
        start_default = today - timedelta(days=365 * 2)
        end_default = today
        start = st.date_input("Start-Datum", value=start_default)
        end = st.date_input("End-Datum", value=end_default)
        submitted = st.form_submit_button(
            "Backtest starten",
            disabled=bool(st.session_state.get("running", False)),
        )

    if not submitted:
        return

    universe_preset: str | None = (
        None if universe_choice == _CUSTOM_TICKER_OPTION else universe_choice
    )
    st.session_state["running"] = True
    log_container = st.empty()
    try:
        with log_container.container(), st.spinner("Backtest laeuft..."):
            run_id, result = runner.run_request(
                strategy_name=strategy,
                ticker=ticker,
                universe_preset=universe_preset,
                start=start,
                end=end,
            )
        metrics = MetricsCalculator().calculate(result)
        report = _to_report(run_id, result, metrics)
        st.success(
            f"Backtest abgeschlossen: Run-ID {run_id} / Final Equity {result.final_equity:,.2f} USD"
        )
        st.plotly_chart(_render_equity_curve(report), use_container_width=True)
        _render_kpi(metrics)
        st.subheader("Trades")
        _render_trades_table(report)
    except UnknownStrategyError as exc:
        available = ", ".join(exc.available) if exc.available else "(keine)"
        st.error(f"Unbekannte Strategie: '{exc.name}'. Verfuegbar: {available}")
    except CacheMissingError as exc:
        st.error(f"{exc}\nTipp: `python -m quant_trader.data {exc.ticker}` aufrufen.")
    except InvalidParamsError as exc:
        st.error(f"Ungueltige Parameter: {exc}")
    except BacktestError as exc:
        st.error(f"Backtest fehlgeschlagen: {exc}")
    except Exception as exc:
        log.exception("backtest.dashboard.unexpected_error", error=str(exc))
        st.error(f"Unerwarteter Fehler: {exc}")
    finally:
        st.session_state["running"] = False


def _to_report(run_id: str, result: BacktestResult, metrics: Metrics | None) -> BacktestReport:
    return BacktestReport(
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


def _render_read_mode(report_loader: ReportLoader) -> None:
    runs = report_loader.list_runs()
    if not runs:
        st.info(
            "Noch keine Backtests gelaufen. Bitte zuerst `python -m quant_trader.backtest run ...` aufrufen."
        )
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
    report = report_loader.load_run(selected_run_id)
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


def _comparison_metric(value: float | int | None) -> float | int | str:
    return "n/a" if value is None else value


def _comparison_dataframe(rows: list[ComparisonRow]) -> pd.DataFrame:
    records: list[dict[str, str | float | int]] = [
        {
            "Strategie": row.strategy_name,
            "Version": row.version or "n/a",
            "letzter Run": row.latest_run_id or "keiner",
            "Total Return %": _comparison_metric(row.total_return_pct),
            "Sharpe": _comparison_metric(row.sharpe),
            "Max Drawdown %": _comparison_metric(row.max_drawdown_pct),
            "CAGR %": _comparison_metric(row.cagr_pct),
            "Trades": _comparison_metric(row.n_trades),
            "Exposure %": _comparison_metric(row.exposure_pct),
        }
        for row in rows
    ]
    return pd.DataFrame(records)


def _render_comparison(report_loader: ReportLoader, strategy_names: list[str]) -> None:
    summaries = latest_runs_by_strategy(report_loader, strategy_names)
    report_count = sum(summary is not None for summary in summaries.values())
    log.info(
        "backtest.comparison.render",
        strategy_count=len(strategy_names),
        report_count=report_count,
    )
    if not strategy_names:
        st.info("Keine Strategien registriert")
        return

    versions = {name: "1.0.0" for name in strategy_names}
    base_rows = ComparisonTable.build_rows(summaries, strategy_versions=versions)
    reports: dict[str, BacktestReport] = {}
    populated_rows: list[ComparisonRow] = []
    for row in base_rows:
        if row.latest_run_id is None:
            populated_rows.append(row)
            continue
        report = report_loader.load_run(row.latest_run_id)
        reports[row.strategy_name] = report
        metrics = report.metrics
        if metrics is None:
            populated_rows.append(row)
            continue
        populated_rows.append(
            replace(
                row,
                total_return_pct=metrics.total_return_pct,
                sharpe=metrics.sharpe_ratio,
                max_drawdown_pct=metrics.max_drawdown_pct,
                cagr_pct=metrics.cagr_pct,
                n_trades=metrics.n_trades,
                exposure_pct=metrics.exposure_pct,
            )
        )

    rows = ComparisonTable.sort_by_sharpe_desc(populated_rows)
    st.subheader("Equity-Curves")
    if not reports:
        st.info("Noch keine Backtests gelaufen")
    else:
        chart_rows = [row for row in rows if row.strategy_name in reports]
        for offset in range(0, len(chart_rows), 2):
            columns = st.columns(2)
            for column, row in zip(columns, chart_rows[offset : offset + 2], strict=False):
                with column:
                    st.plotly_chart(
                        _render_comparison_equity_curve(reports[row.strategy_name]),
                        use_container_width=True,
                    )

    st.subheader("Strategie-Vergleich")
    st.dataframe(_comparison_dataframe(rows), use_container_width=True, hide_index=True)
    for row in rows:
        action_columns = st.columns([3, 1])
        action_columns[0].write(row.strategy_name)
        if action_columns[1].button(
            "Backtest starten",
            key=f"comparison-start-{row.strategy_name}",
            use_container_width=True,
        ):
            st.session_state.active_tab = 0
            st.session_state.prefill_strategy = row.strategy_name
            st.rerun()


def _tab_default(tab_labels: list[str]) -> str | None:
    requested_index = st.session_state.pop("active_tab", None)
    if not isinstance(requested_index, int) or not 0 <= requested_index < len(tab_labels):
        return None
    st.session_state.pop("tabs", None)
    return tab_labels[requested_index]


def main() -> None:
    configure_logging("INFO")
    _reports_dir()
    st.set_page_config(page_title="QuantTrader - Backtest Dashboard", layout="wide")
    st.title("QuantTrader - Backtest Dashboard")

    report_loader, runner, strategy_names, preset_names = _build_services()
    tab_labels = [_RUN_FORM_TAB, _READ_MODE_TAB, _COMPARISON_TAB]
    tab_run, tab_read, tab_comparison = st.tabs(
        tab_labels,
        default=_tab_default(tab_labels),
        key="tabs",
    )
    with tab_run:
        _render_run_form(runner, strategy_names, preset_names)
    with tab_read:
        _render_read_mode(report_loader)
    with tab_comparison:
        _render_comparison(report_loader, strategy_names)


if __name__ == "__main__":
    main()
