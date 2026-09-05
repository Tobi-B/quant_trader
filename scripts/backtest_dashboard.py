"""Streamlit-Dashboard: interactive browser view over the backtest system.

Start: `uv run streamlit run scripts/backtest_dashboard.py`
Requires the `ui` extra: `uv sync --extra ui`.

Tabs:
- "Run-Form" (US-P3.9): pick strategy + ticker/universe + date range, click
  "Backtest starten", see the result (KPIs + equity curve + trades) right
  under the form in the same tab. Im Custom-Ticker-Modus ermoeglicht eine
  Unternehmens- und Ticker-Suche (US-P3.11) das Auffinden unbekannter Ticker
  via FMP `search`-Endpoint.
- "Read-Mode" (US-P3.7): browse past backtest reports from `reports/`.
- "Vergleich" (US-P3.10): compare the latest report for every registered strategy.
- "Cache" (US-P1.9): bulk refresh the parquet cache (alle gecachten Tickers,
  Universe-Preset, freie Ticker-Liste).
- "Katalog" (US-P1.10..13): zentraler Instrumentkatalog aus NASDAQ Trader,
  Xetra und CoinGecko; Suche, Filter, benannte Universen, Standard-Universen.
- "Strategien" (US-P2.8): pro registrierter Strategie eine README mit
  Parametern und Risiken.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

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
from quant_trader.core.errors import (
    CatalogRefreshError,
    CatalogUnavailableError,
    EmptyUniverseSelectionError,
    SearchUnavailableError,
)
from quant_trader.core.logging import configure_logging, get_logger
from quant_trader.core.types import Granularity, Instrument
from quant_trader.data.cache import ParquetCache
from quant_trader.data.factory import build_chain
from quant_trader.data.financial_modelling_prep import FinancialModellingPrepProvider
from quant_trader.data.instrument_catalog import (
    CatalogStatus,
    FilterOptions,
    InstrumentCatalogService,
    InstrumentCatalogSnapshotStore,
)
from quant_trader.data.instrument_search import (
    CompanySearchService,
    FmpProfilePhantomValidator,
)
from quant_trader.data.public_catalog import PublicCatalogProvider
from quant_trader.data.refresh import RefreshSummary, refresh_tickers
from quant_trader.strategies import StrategyDocLoader, default_loader
from quant_trader.strategies.base import StrategyBase
from quant_trader.strategies.loader import StrategyLoader
from quant_trader.universe.dynamic_store import DynamicUniverseStore
from quant_trader.universe.presets import PresetRepository

if TYPE_CHECKING:
    from quant_trader.data.provider import DataProvider

log = get_logger(__name__)

_REPORTS_DIR = Path("./reports")
_CUSTOM_TICKER_OPTION = "(Custom-Ticker)"
_STRATEGY_DEFAULT_UNIVERSE_OPTION = "(Strategie-Standard)"
_RUN_FORM_TAB = "Run-Form"
_READ_MODE_TAB = "Read-Mode"
_COMPARISON_TAB = "Vergleich"
_CACHE_TAB = "Cache"
_CATALOG_TAB = "Katalog"
_STRATEGIES_TAB = "Strategien"
_FILTER_ALL_OPTION = "(Alle)"
_STANDARD_UNIVERSE_NAMES = ("sp500", "etfs")
_CACHE_MODE_ALL = "Alle gecachten Tickers"
_CACHE_MODE_UNIVERSE = "Universe"
_CACHE_MODE_TICKERS = "Ticker-Liste"
_CACHE_MODES = [_CACHE_MODE_ALL, _CACHE_MODE_UNIVERSE, _CACHE_MODE_TICKERS]
_SEARCH_QUERY_KEY = "instrument_search_query"
_SEARCH_RESULTS_KEY = "instrument_search_results"
_SEARCH_RESULTS_QUERY_KEY = "instrument_search_results_query"
_SEARCH_COMPLETED_QUERY_KEY = "instrument_search_completed_query"
_SEARCH_ERROR_KEY = "instrument_search_error"
_TICKER_KEY = "run_ticker"


def _reports_dir() -> Path:
    settings = get_settings()
    log.info("dashboard.start", reports_dir=str(_REPORTS_DIR), data_dir=str(settings.data_dir))
    return _REPORTS_DIR


@st.cache_resource(show_spinner=False)
def _build_services() -> tuple[
    ReportLoader,
    DashboardRunner,
    CompanySearchService,
    list[str],
    list[str],
    InstrumentCatalogService,
    DynamicUniverseStore,
]:
    """Build the long-lived services once per Streamlit session."""
    settings = get_settings()
    loader = default_loader()
    presets = PresetRepository(settings.universe_presets_path)
    dynamic_store = DynamicUniverseStore(settings.dynamic_universes_path)
    orchestrator = BacktestOrchestrator(
        cache=ParquetCache(settings.data_dir),
        loader=loader,
        reports_dir=_REPORTS_DIR,
    )
    runner = DashboardRunner(
        orchestrator=orchestrator, loader=loader, presets=presets, dynamic_store=dynamic_store
    )
    search_service = CompanySearchService(
        FinancialModellingPrepProvider(api_key=settings.fmp_api_key),
        phantom_validator=FmpProfilePhantomValidator(api_key=settings.fmp_api_key),
    )
    catalog_service = InstrumentCatalogService(
        PublicCatalogProvider(),
        InstrumentCatalogSnapshotStore(settings.catalog_path),
        dynamic_store,
        refresh_interval=timedelta(hours=settings.catalog_max_age_hours),
    )
    strategy_names = loader.registered_names()
    preset_names = presets.names()
    return (
        ReportLoader(_REPORTS_DIR),
        runner,
        search_service,
        strategy_names,
        preset_names,
        catalog_service,
        dynamic_store,
    )


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


def _instrument_label(instrument: Instrument) -> str:
    return f"{instrument.name} - {instrument.ticker} ({instrument.exchange})"


def _render_instrument_search(search_service: CompanySearchService) -> None:
    st.caption("Unternehmen oder ETF suchen, wenn der Ticker unbekannt ist.")
    query = st.text_input(
        "Unternehmensname oder Ticker",
        key=_SEARCH_QUERY_KEY,
        placeholder="z.B. Apple oder AAPL",
    )
    normalized_query = query.strip()
    search_clicked = st.button(
        "Unternehmen suchen",
        key="instrument_search_button",
        disabled=not bool(normalized_query),
    )

    if search_clicked:
        try:
            results = search_service.search(normalized_query)
        except SearchUnavailableError:
            st.session_state[_SEARCH_RESULTS_KEY] = []
            st.session_state[_SEARCH_RESULTS_QUERY_KEY] = normalized_query
            st.session_state[_SEARCH_COMPLETED_QUERY_KEY] = normalized_query
            st.session_state[_SEARCH_ERROR_KEY] = normalized_query
        else:
            st.session_state[_SEARCH_RESULTS_KEY] = results
            st.session_state[_SEARCH_RESULTS_QUERY_KEY] = normalized_query
            st.session_state[_SEARCH_COMPLETED_QUERY_KEY] = normalized_query
            st.session_state[_SEARCH_ERROR_KEY] = None

    if st.session_state.get(_SEARCH_ERROR_KEY) == normalized_query:
        st.error(
            "Die Unternehmenssuche ist vorübergehend nicht verfügbar. "
            "Du kannst den Ticker unten manuell eingeben."
        )

    result_query = st.session_state.get(_SEARCH_RESULTS_QUERY_KEY)
    raw_results = st.session_state.get(_SEARCH_RESULTS_KEY, [])
    results = (
        [result for result in raw_results if isinstance(result, Instrument)]
        if result_query == normalized_query
        else []
    )
    if (
        not results
        and st.session_state.get(_SEARCH_COMPLETED_QUERY_KEY) == normalized_query
        and st.session_state.get(_SEARCH_ERROR_KEY) != normalized_query
    ):
        st.info(f"Keine Treffer für '{normalized_query}'. Bitte Suchbegriff ändern.")
    if not results:
        return

    selected_index = st.selectbox(
        "Suchtreffer auswählen",
        options=list(range(len(results))),
        format_func=lambda index: _instrument_label(results[index]),
        key="instrument_search_selected",
    )
    if st.button("Auswahl übernehmen", key="instrument_search_apply"):
        st.session_state[_TICKER_KEY] = results[selected_index].ticker
        st.session_state[_SEARCH_RESULTS_KEY] = []
        st.session_state[_SEARCH_RESULTS_QUERY_KEY] = None
        st.session_state[_SEARCH_COMPLETED_QUERY_KEY] = None
        st.session_state[_SEARCH_ERROR_KEY] = None
        st.rerun()


def _render_run_form(
    runner: DashboardRunner,
    search_service: CompanySearchService,
    strategy_names: list[str],
    preset_names: list[str],
    loader: StrategyLoader,
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
    with st.sidebar:
        st.header("Backtest-Konfiguration")
        strategy = st.selectbox(
            "Strategie", strategy_names, index=strategy_index, key="run_form_strategy"
        )
        strategy_cls = loader.get_class(strategy)
        is_single_ticker = issubclass(strategy_cls, StrategyBase)
        supports_override = bool(getattr(strategy_cls, "supports_universe_override", True))

        ticker = ""
        universe_choice = _CUSTOM_TICKER_OPTION
        if is_single_ticker:
            # A single-ticker strategy runs on exactly one ticker - there is
            # no "universe" concept for it, so Universe-Preset never applies.
            _render_instrument_search(search_service)
            ticker = st.text_input(
                "Ticker",
                key=_TICKER_KEY,
                placeholder="z.B. SPY",
            )
        elif supports_override:
            # Multi-ticker strategies never read the Ticker field (the
            # strategy is instantiated without it), so only a universe
            # selector makes sense here - not a ticker input.
            universe_options = [_STRATEGY_DEFAULT_UNIVERSE_OPTION, *preset_names]
            universe_choice = st.selectbox(
                "Universe-Preset", universe_options, key="run_form_universe_preset"
            )
        else:
            st.caption(
                f"'{strategy}' bezieht sein Universe aus mehreren eigenen Parametern "
                "(siehe Tab 'Strategien') und kann hier nicht ueberschrieben werden."
            )
        with st.form(key="run_form"):
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
        None
        if universe_choice in (_CUSTOM_TICKER_OPTION, _STRATEGY_DEFAULT_UNIVERSE_OPTION)
        else universe_choice
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

    st.subheader("Backtest-Auswahl")
    strategy_options = sorted({r.strategy_name for r in runs if r.strategy_name})
    if not strategy_options:
        st.info("Keine laufenden Strategien gefunden.")
        return
    select_cols = st.columns(2)
    selected_strategy = select_cols[0].selectbox(
        "Strategie", strategy_options, key="read_mode_strategy"
    )
    filtered = [r for r in runs if r.strategy_name == selected_strategy]
    if not filtered:
        st.info(f"Keine Runs fuer Strategie '{selected_strategy}'.")
        return
    run_options = [r.run_id for r in filtered]
    selected_run_id = select_cols[1].selectbox("Run", run_options, key="read_mode_run")
    st.divider()
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


def _build_cache_services() -> tuple[ParquetCache, DataProvider, list[str]]:
    settings = get_settings()
    cache = ParquetCache(settings.data_dir)
    provider = build_chain(settings)
    preset_repo = PresetRepository(settings.universe_presets_path)
    return cache, provider, preset_repo.names()


def _resolve_tickers(
    mode: str,
    universe_input: str,
    ticker_input: str,
    cache: ParquetCache,
    preset_names: list[str],
) -> list[str]:
    if mode == _CACHE_MODE_ALL:
        return list(cache.list_cached_tickers(Granularity.DAILY))
    if mode == _CACHE_MODE_UNIVERSE:
        settings = get_settings()
        preset = PresetRepository(settings.universe_presets_path).get(universe_input)
        return [t.upper() for t in preset.tickers]
    return [t.strip().upper() for t in ticker_input.split(",") if t.strip()]


def _render_summary_details(summary: RefreshSummary) -> None:
    if not summary.details:
        st.info("Keine Tickers verarbeitet.")
        return
    records: list[dict[str, str | float]] = []
    for detail in summary.details:
        records.append(
            {
                "Ticker": detail.ticker,
                "Status": detail.status,
                "Bars hinzugefuegt": detail.bars_added,
                "Fehler": detail.error_message or "",
                "Dauer (s)": round(detail.duration_seconds, 3),
            }
        )
    st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)


def _render_strategies_tab(doc_loader: StrategyDocLoader, strategy_loader: StrategyLoader) -> None:
    """Render the "Strategien" tab: per-strategy README + default params."""
    names = strategy_loader.registered_names()
    st.subheader("Registrierte Strategien")
    st.caption(
        "Ausfuehrliche Erklaerung jeder registrierten Strategie auf Basis "
        "der README-Dateien unter docs/strategies/."
    )
    if names:
        st.selectbox(
            "Springe zu Strategie",
            options=names,
            key="strategies_jump_to",
            index=0,
        )
    if not names:
        st.info("Keine Strategien registriert")
        log.info("dashboard.strategies.rendered", count=0, documented=0)
        return

    documented = 0
    for name in names:
        cls = strategy_loader.get_class(name)
        version = getattr(cls, "version", "1.0.0")
        st.subheader(f"{name} (v{version})")
        doc = doc_loader.load(name)
        if doc is None:
            st.warning(
                f"Keine Doku vorhanden fuer '{name}'. Bitte erstelle docs/strategies/{name}.md"
            )
        else:
            st.markdown(doc)
            documented += 1
        params = cls.default_params
        if params:
            records = [{"Parameter": key, "Default": value} for key, value in params.items()]
            st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
        else:
            st.caption("Keine Parameter")
    log.info(
        "dashboard.strategies.rendered",
        count=len(names),
        documented=documented,
    )


def _render_cache_tab(cache: ParquetCache, provider: DataProvider, preset_names: list[str]) -> None:
    st.subheader("Cache aktualisieren")
    today = date.today()
    default_start = today - timedelta(days=365 * 10)

    with st.form(key="cache_refresh_form"):
        mode = st.radio(
            "Modus",
            _CACHE_MODES,
            index=0,
            key="cache_mode",
        )
        universe_input = ""
        if mode == _CACHE_MODE_UNIVERSE:
            if preset_names:
                universe_input = st.selectbox("Universe-Preset", preset_names, key="cache_universe")
            else:
                st.warning("Keine Universe-Presets gefunden.")
                universe_input = ""
        ticker_input = ""
        if mode == _CACHE_MODE_TICKERS:
            ticker_input = st.text_input(
                "Ticker (Komma-getrennt)",
                value="SPY,AGG",
                key="cache_tickers",
            )
        start = st.date_input("Start-Datum", value=default_start, key="cache_start")
        end = st.date_input("End-Datum", value=today, key="cache_end")
        submitted = st.form_submit_button(
            "Refresh starten",
            type="primary",
            disabled=bool(st.session_state.get("cache_refreshing", False)),
        )

    if not submitted:
        return

    if start >= end:
        st.error("Start-Datum muss vor End-Datum liegen.")
        return

    tickers = _resolve_tickers(mode, universe_input, ticker_input, cache, preset_names)
    if not tickers:
        st.warning("Keine Ticker fuer den gewaehlten Modus gefunden.")
        return

    st.session_state["cache_refreshing"] = True
    progress = st.progress(0.0, text="Starte Refresh...")
    log_placeholder = st.empty()
    progress_lines: list[str] = []

    def _emit(text: str) -> None:
        progress_lines.append(text)
        log_placeholder.code("\n".join(progress_lines[-10:]), language="text")

    total = len(tickers)
    details: list = []
    for index, ticker in enumerate(tickers, start=1):
        progress.progress(
            (index - 1) / total,
            text=f"({index - 1}/{total}) {ticker}",
        )
        _emit(f"-> {ticker}: fetch startet")
        try:
            partial = refresh_tickers(
                [ticker],
                cache,
                provider,
                Granularity.DAILY,
                start=start,
                end=end,
            )
            details.extend(partial.details)
            for detail in partial.details:
                if detail.status == "error":
                    st.error(f"{detail.ticker}: {detail.error_message}")
                    _emit(f"!! {detail.ticker}: {detail.error_message}")
                else:
                    _emit(
                        f"OK {detail.ticker}: {detail.status} (+{detail.bars_added}) "
                        f"in {detail.duration_seconds:.2f}s"
                    )
        except Exception as exc:
            log.exception("data.refresh.dashboard_error", ticker=ticker, error=str(exc))
            st.error(f"{ticker}: {exc}")
            _emit(f"!! {ticker}: {exc}")
        progress.progress(index / total, text=f"({index}/{total}) {ticker} fertig")

    progress.progress(1.0, text="Refresh abgeschlossen")
    st.session_state["cache_refreshing"] = False

    updated = sum(1 for d in details if d.status == "updated")
    unchanged = sum(1 for d in details if d.status == "unchanged")
    errors = sum(1 for d in details if d.status == "error")
    duration = sum(d.duration_seconds for d in details)
    summary = RefreshSummary(
        total=len(details),
        updated=updated,
        unchanged=unchanged,
        errors=errors,
        duration_seconds=duration,
        details=details,
    )
    log.info(
        "data.refresh.complete",
        total=summary.total,
        updated=summary.updated,
        unchanged=summary.unchanged,
        errors=summary.errors,
        duration_s=round(summary.duration_seconds, 3),
    )
    st.success(
        f"{updated} aktualisiert, {unchanged} unveraendert, {errors} Fehler in {duration:.1f}s"
    )
    _render_summary_details(summary)


def _render_catalog_status(
    status: CatalogStatus, catalog_service: InstrumentCatalogService
) -> None:
    if status.snapshot_id is None:
        st.warning("Noch kein Instrumentkatalog vorhanden.")
    else:
        age_text = (
            "unbekannt" if status.age is None else f"{status.age.total_seconds() / 3600:.1f}h"
        )
        st.caption(f"{status.total} Instrumente im Katalog  |  Alter: {age_text}")
        if status.needs_refresh:
            st.warning(f"Katalog ist veraltet (Alter: {age_text}). Aktualisierung empfohlen.")

    disabled = bool(st.session_state.get("catalog_refreshing", False))
    if st.button("Katalog aktualisieren", key="catalog_refresh_button", disabled=disabled):
        st.session_state["catalog_refreshing"] = True
        try:
            with st.spinner("Katalog wird aktualisiert..."):
                result = catalog_service.refresh(force=True)
        except CatalogUnavailableError as exc:
            st.error(f"Katalog nicht verfuegbar: {exc.reason}")
        except CatalogRefreshError as exc:
            st.error(f"Katalog-Aktualisierung fehlgeschlagen: {exc.reason}")
        else:
            if result.used_fallback:
                st.warning("Aktualisierung fehlgeschlagen, letzter bekannter Stand wird verwendet.")
            else:
                st.success(
                    f"Katalog aktualisiert: {result.total} Instrumente "
                    f"(+{result.added}/-{result.removed})"
                )
        finally:
            st.session_state["catalog_refreshing"] = False


def _filter_value(selection: str) -> str | None:
    return None if selection == _FILTER_ALL_OPTION else selection


def _catalog_results_dataframe(results: list[Instrument]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Symbol": i.ticker,
                "Name": i.name,
                "Boerse": i.exchange,
                "Land": i.country,
                "Instrumentart": i.instrument_type,
            }
            for i in results
        ]
    )


def _render_catalog_search(
    catalog_service: InstrumentCatalogService,
    dynamic_store: DynamicUniverseStore,
) -> None:
    try:
        options: FilterOptions | None = catalog_service.list_filter_options()
    except CatalogUnavailableError:
        options = None

    query = st.text_input(
        "Suche (Symbol oder Name, z.B. BRK.B)", key="catalog_query", placeholder="z.B. BRK.B"
    )

    selected_type = selected_country = selected_exchange = selected_sector = _FILTER_ALL_OPTION
    if options is not None:
        cols = st.columns(4)
        selected_type = cols[0].selectbox(
            "Instrumentart",
            [_FILTER_ALL_OPTION, *options.instrument_types],
            key="catalog_filter_type",
        )
        selected_country = cols[1].selectbox(
            "Land", [_FILTER_ALL_OPTION, *options.countries], key="catalog_filter_country"
        )
        selected_exchange = cols[2].selectbox(
            "Boerse", [_FILTER_ALL_OPTION, *options.exchanges], key="catalog_filter_exchange"
        )
        selected_sector = cols[3].selectbox(
            "Sektor", [_FILTER_ALL_OPTION, *options.sectors], key="catalog_filter_sector"
        )

    if st.button("Suchen", key="catalog_search_button"):
        try:
            results = catalog_service.search(
                query,
                limit=200,
                instrument_type=_filter_value(selected_type),
                country=_filter_value(selected_country),
                exchange=_filter_value(selected_exchange),
                sector=_filter_value(selected_sector),
            )
        except CatalogUnavailableError:
            st.error(
                "Der Instrumentkatalog ist noch nicht verfuegbar. "
                "Bitte zuerst 'Katalog aktualisieren' ausfuehren."
            )
            st.session_state["catalog_results"] = []
        else:
            st.session_state["catalog_results"] = results

    results = st.session_state.get("catalog_results", [])
    if not results:
        return

    st.dataframe(_catalog_results_dataframe(results), use_container_width=True, hide_index=True)

    universe_name = st.text_input("Name fuer neues Universe", key="catalog_universe_name")
    save_clicked = st.button("In Universe uebernehmen", key="catalog_universe_save")
    pending = st.session_state.get("catalog_pending_overwrite")

    if save_clicked and universe_name.strip():
        filters = {
            key: value
            for key, value in {
                "instrument_type": _filter_value(selected_type),
                "country": _filter_value(selected_country),
                "exchange": _filter_value(selected_exchange),
                "sector": _filter_value(selected_sector),
            }.items()
            if value is not None
        }
        try:
            universe = catalog_service.build_dynamic_universe(
                universe_name.strip(),
                filters=filters,
                query=query,
                description=f"Katalog-Suche: '{query}'" if query else "Katalog-Filter",
            )
        except EmptyUniverseSelectionError:
            st.warning("Die aktuelle Auswahl enthaelt keine Instrumente. Nichts gespeichert.")
        else:
            if dynamic_store.exists(universe.name):
                st.session_state["catalog_pending_overwrite"] = universe
                st.warning(f"Universe '{universe.name}' existiert bereits. Ersetzen?")
            else:
                dynamic_store.save(universe)
                st.success(
                    f"Universe '{universe.name}' gespeichert ({len(universe.tickers)} Ticker)."
                )

    if pending is not None and st.button("Ja, ersetzen", key="catalog_universe_confirm_overwrite"):
        dynamic_store.save(pending, overwrite=True)
        st.session_state["catalog_pending_overwrite"] = None
        st.success(f"Universe '{pending.name}' ersetzt ({len(pending.tickers)} Ticker).")


def _render_standard_universes(catalog_service: InstrumentCatalogService) -> None:
    st.subheader("Standard-Universen")
    cols = st.columns(3)
    if cols[0].button("DAX 40 aktualisieren", key="catalog_standard_dax40"):
        try:
            universe = catalog_service.build_standard_universe("dax40")
        except (CatalogUnavailableError, EmptyUniverseSelectionError) as exc:
            st.error(f"DAX 40 konnte nicht gebaut werden: {exc}")
        else:
            st.success(f"'dax40' aktualisiert ({len(universe.tickers)} Ticker).")
            st.caption(
                "Quelle ist die DAX-Handelsgruppe der Deutschen Boerse. Sie enthaelt "
                "auch die jeweils zweite Aktiengattung (z.B. VOW und VOW3), also "
                "etwas mehr als die 40 Indexmitglieder."
            )
    if cols[1].button("ETFs aktualisieren", key="catalog_standard_etfs"):
        try:
            universe = catalog_service.build_standard_universe("etfs")
        except (CatalogUnavailableError, EmptyUniverseSelectionError) as exc:
            st.error(f"ETFs konnten nicht gebaut werden: {exc}")
        else:
            st.success(f"'etfs' aktualisiert ({len(universe.tickers)} Ticker).")
    cols[2].info(
        "S&P 500 bleibt statisch: die Indexzusammensetzung ist ein "
        "lizenziertes Produkt und in keiner freien Quelle enthalten."
    )


def _render_catalog_tab(
    catalog_service: InstrumentCatalogService,
    dynamic_store: DynamicUniverseStore,
) -> None:
    st.subheader("Instrumentkatalog")
    st.caption(
        "Zentraler, taeglich aktualisierter Katalog aus NASDAQ Trader (US-Aktien "
        "und -ETFs), Deutsche Boerse Xetra (EU-Instrumente inkl. DAX) und "
        "CoinGecko (Kryptowaehrungen)."
    )
    status = catalog_service.snapshot_status()
    _render_catalog_status(status, catalog_service)
    st.divider()
    _render_catalog_search(catalog_service, dynamic_store)
    st.divider()
    _render_standard_universes(catalog_service)


def main() -> None:
    configure_logging("INFO")
    _reports_dir()
    st.set_page_config(page_title="QuantTrader - Backtest Dashboard", layout="wide")
    st.title("QuantTrader - Backtest Dashboard")

    (
        report_loader,
        runner,
        search_service,
        strategy_names,
        preset_names,
        catalog_service,
        dynamic_store,
    ) = _build_services()
    cache, provider, cache_preset_names = _build_cache_services()
    loader = default_loader()
    tab_labels = [
        _RUN_FORM_TAB,
        _READ_MODE_TAB,
        _COMPARISON_TAB,
        _CACHE_TAB,
        _CATALOG_TAB,
        _STRATEGIES_TAB,
    ]
    tab_run, tab_read, tab_comparison, tab_cache, tab_catalog, tab_strategies = st.tabs(
        tab_labels,
        default=_tab_default(tab_labels),
        key="tabs",
    )
    with tab_run:
        _render_run_form(runner, search_service, strategy_names, preset_names, loader)
    with tab_read:
        _render_read_mode(report_loader)
    with tab_comparison:
        _render_comparison(report_loader, strategy_names)
    with tab_cache:
        _render_cache_tab(cache, provider, cache_preset_names)
    with tab_catalog:
        _render_catalog_tab(catalog_service, dynamic_store)
    with tab_strategies:
        doc_loader = StrategyDocLoader(get_settings().strategy_docs_dir)
        _render_strategies_tab(doc_loader, loader)


if __name__ == "__main__":
    main()
