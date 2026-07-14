# PRD: Slice 3.3 - Report (Console + Plotly HTML + JSON + Streamlit-Dashboard)

Phase:    P3 Backtest-Engine + Reports
Slice:    3.3 Report
Status:   DRAFT  (User "ja starten" gilt als implizite Approval; UML auf APPROVED setzen)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Abgeschlossene `BacktestResult` in vier komplementaere Output-Formate
bringen: formatierte Console-Tabelle (US-P3.4), interaktives Plotly-HTML
(US-P3.5), persistentes JSON (US-P3.6) und read-only Streamlit-Dashboard
(US-P3.7). Dadurch kann der Trader das Ergebnis ohne File-Output schnell
bewerten, im Browser explorieren und/oder programmatisch weiterverarbeiten.

## Scope (IN)

- `quant_trader.backtest.report` Sub-Package:
  - `__init__.py` mit Public-API
  - `types.py`:
    - `ReportPaths` (frozen dataclass: equity_html: Path, result_json: Path)
    - `RunSummary` (frozen dataclass: run_id, strategy_name, start, end, final_equity, sharpe)
    - `BacktestReport` (frozen dataclass: run_id, strategy_name, params, start, end, fill_mode, initial_cash, final_equity, metrics: Metrics, equity_curve: list[EquitySnapshot], trades: list[Trade])
  - `console.py`:
    - `ConsoleFormatter` mit:
      - `format_metrics(metrics: Metrics) -> str` (formatierte Tabelle)
      - `format_trades(trades: list[Trade], top: int = 10) -> str` (Top-Trades-Tabelle)
      - `format_report(result: BacktestResult, metrics: Metrics, top: int = 10) -> str` (Metrik + Top-Trades)
    - Fixed-width Spalten, deterministisch, deutsche Texte (NFR-Ux-1)
    - Bei Empty-Run: Tabelle zeigt "keine Trades" ohne Crash
  - `plotly_exporter.py`:
    - `PlotlyExporter` mit `export_equity_curve(report: BacktestReport, path: Path) -> Path`
    - HTML self-contained (Plotly-JS via CDN oder inline)
    - X=Date, Y=Equity, Hover mit Datum + Equity + Position-Snapshot
    - Bei Empty-Run: leere Figure mit Hinweis "Keine Trades"
  - `json_exporter.py`:
    - `JsonExporter` mit `export(report: BacktestReport, path: Path) -> Path`
    - Schema: strategy_name, params, start, end, fill_mode, initial_cash, final_equity, metrics (alle Felder, mit None wo applicable), equity_curve (Liste von {date, equity, cash, positions}), trades (Liste von {ticker, entry_date, entry_price, exit_date, exit_price, pnl, pnl_pct})
    - Dates als ISO-Strings, floats als Number
    - Stabile Schema (typed dict, keine Sets/Objects)
  - `loader.py`:
    - `ReportLoader(reports_dir: Path)` mit:
      - `list_runs() -> list[RunSummary]`
      - `load_run(run_id: str) -> BacktestReport`
    - Liest `result.json` aus `reports/<run_id>/`, baut `BacktestReport`
  - `builder.py`:
    - `ReportBuilder(metrics_calc: MetricsCalculator | None = None)` mit:
      - `build(result: BacktestResult, output_dir: Path, run_id: str) -> ReportPaths`
      - Berechnet Metrics via `MetricsCalculator`
      - Erzeugt BacktestReport, ruft PlotlyExporter + JsonExporter
      - Returns ReportPaths
- `scripts/backtest_dashboard.py`:
  - Streamlit-Dashboard (read-only) mit:
    - Sidebar: Strategie-Selector (Dropdown aus RunSummary.strategy_name), Run-Selector (Dropdown aus RunSummary.run_id)
    - Hauptbereich: Equity-Curve (Plotly), KPI-Indikatoren (Sharpe, MDD, Total Return, CAGR), Top-Trades-Tabelle
    - Wenn `reports/` leer: st.info("Noch keine Backtests gelaufen")
    - Nur lesend (kein Run-Button; kommt mit Slice 3.5)
- `quant_trader.backtest.__init__.py`: exportiert ConsoleFormatter, PlotlyExporter, JsonExporter, ReportBuilder, ReportLoader, BacktestReport
- Tests: `tests/backtest/test_report/`:
  - `test_console.py`: format_metrics, format_trades, format_report, empty-run, fixed-width determinism
  - `test_plotly.py`: export_equity_curve, file written, html contains expected markers, empty-run
  - `test_json.py`: roundtrip (write+read), schema, types, dates-as-iso
  - `test_loader.py`: list_runs, load_run, missing dir
  - `test_builder.py`: build() orchestriert, ReportPaths korrekt, files exist

## Out of Scope (verbindlich)

- CSV-Export der Trades (US-P3.4 Out-of-Scope)
- Sort/Filter-UI im Streamlit-Dashboard (US-P3.7 Out-of-Scope)
- Run-Trigger im Dashboard (US-P3.9 / Slice 3.5)
- Parquet-Export (US-P3.6 Out-of-Scope)
- Drawdown-Chart im HTML (US-P3.5 Out-of-Scope; kommt spaeter)
- Vergleichs-Overlay mehrerer Runs (US-P3.7 Out-of-Scope)
- Login / User-Management
- Persistenz in DB (kommt mit Phase 5)
- Backtest-CLI (`python -m quant_trader.backtest`) - Slice 3.4

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies (plotly ist bereits in pyproject.toml).
- Kein `print`, kein globaler State.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, CLI-/UI-Strings deutsch (NFR-Ux-1).
- Console-Tabelle: fixed-width, deterministisch (gleiche Inputs -> gleicher Output, testbar).
- HTML self-contained: Plotly-JS via CDN (https://cdn.plot.ly/plotly-2.x.x.min.js) ist OK,
  file darf nicht von lokalen Resourcen abhaengen, die nicht im Repo sind.
- JSON Schema v1: stabile Top-Level-Keys, floats als Number, dates als ISO-String.
- Streamlit ist optional (ui extra) - Import-Tests muessen guarded sein.
- Tests fuer Streamlit-Code: Smoke-Import-Test + dry-run, keine echte Browser-Oeffnung.

## Mapped NFRs

- NFR-Ux-1: Deutsche Texte in Console und Dashboard.
- NFR-Data-2: Equity-HTML nutzt Adj. Close (kommt aus EquitySnapshot.equity).

## UML-Referenz

Visualisiert in: `docs/uml/p3-backtest/report.md` (Status: wird auf
APPROVED gesetzt mit diesem Slice).

## Done when

- [ ] `src/quant_trader/backtest/report/` mit allen Modulen gemaess Scope.
- [ ] `src/quant_trader/backtest/__init__.py` exportiert Public-API.
- [ ] `scripts/backtest_dashboard.py` laedt Reports und rendert Streamlit-UI.
- [ ] Tests in `tests/backtest/test_report/` decken alle Exporter ab.
- [ ] `make test` gruen.
- [ ] `make lint` gruen.
- [ ] `uv run mypy` gruen (ohne pre-existing logging.py).
- [ ] Streamlit smoke: `uv run streamlit run scripts/backtest_dashboard.py` startet
      ohne Crash (manueller Test, keine Browser-Assertion).
- [ ] Conventional Commit `feat(p3-backtest): slice 3.3 report`.
- [ ] `docs/STATE.md` aktualisiert: Slice 3.3 auf DONE, Tag `p3-backtest/3.3`.

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p3-backtest/backtest.md
cat docs/uml/p3-backtest/report.md
cat docs/prd/p3-backtest/report.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. Run-Trigger kommt in 3.5,
  CLI in 3.4.
- Streamlit-Code mit try/except ImportError umschliessen (ui extra).

Nach dem Coden:
- Conventional Commit mit `feat(p3-backtest): slice 3.3 report`.
- Commit-Body: warum ConsoleFormatter fixed-width (Determinismus fuer Tests),
  warum JSON-Schema v1 mit ISO-Dates.
