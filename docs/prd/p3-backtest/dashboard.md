# PRD: Slice 3.5 - Interaktives Backtest-Dashboard (Run-Trigger)

Phase:    P3 Backtest-Engine + Reports
Slice:    3.5 Interaktives Backtest-Dashboard
Status:   DRAFT  (User-Instruction am 2026-07-14 gilt als Approval; UML bereits APPROVED)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Das in Slice 3.3 gebaute read-only Streamlit-Dashboard so erweitern, dass
der Trader einen Backtest direkt im Browser auswaehlen, starten und das
Ergebnis im selben Tab sehen kann. Dazu wird der bestehende
`BacktestOrchestrator` aus Slice 3.4 ueber einen dedizierten
`DashboardRunner` angetriggert; UI-Felder fuer Fill-Mode, Initial-Cash
und Granularity bleiben bewusst ausserhalb (CLI-/YAML-Defaults), damit
der Scope klein bleibt.

## Scope (IN)

- `src/quant_trader/backtest/dashboard_runner.py` (NEU):
  - `DashboardRunner(orchestrator: BacktestOrchestrator, loader: StrategyLoader, presets: PresetRepository)`
  - `run_request(strategy_name: str, ticker: str, universe_preset: str | None, start: date, end: date) -> BacktestResult`
  - Logik:
    1. Strategie pruefen via `loader.is_registered(strategy_name)`; sonst `UnknownStrategyError`
    2. Wenn `universe_preset`: Ticker aus `presets.get(name).tickers` (uppercase)
       Sonst: ticker (uppercase, validiert dass nicht leer)
    3. Wenn ticker leer UND kein universe: `InvalidParamsError("Ticker oder Universe-Preset erforderlich")`
    4. `run_id` generieren via `datetime.now().strftime("%Y%m%dT%H%M%S")`
    5. `orchestrator.run(run_id, strategy_name, ticker=ticker, universe=universe_preset, start, end)` mit Defaults `FillMode.NEXT_OPEN`, `Granularity.DAILY`, `initial_cash=100_000.0`
    6. Strukturiertes Logging: `backtest.dashboard.start`, `backtest.dashboard.complete`
    7. `CacheMissingError` wird durchgereicht (UI faengt es ab)
  - Errors: `UnknownStrategyError`, `InvalidParamsError`, `CacheMissingError`, `BacktestError` (von Orchestrator/Engine)
- `scripts/backtest_dashboard.py` (ERWEITERN, nicht ersetzen):
  - Streamlit-Import bleibt `try/except ImportError` + `SystemExit`
  - `st.tabs(["Run-Form", "Read-Mode"])`
  - **Tab "Run-Form"**:
    - Sidebar: Strategie-Selectbox (`loader.registered_names()`), Universe-Selectbox
      (`presets.names()` + Option "Custom-Ticker"), Ticker-Text-Input (nur sichtbar
      wenn universe = "Custom"), Start/End Date-Input
    - "Backtest starten" Button; `disabled` waehrend Run laeuft (Session-State `running`)
    - Klick -> `DashboardRunner.run_request(...)` -> `st.spinner(...)` + Live-Log-Stream (`st.empty()`)
    - Bei Erfolg: Metriken (4-spaltig via `st.metric`), Equity-Curve (Plotly), Top-Trades-Tabelle (`st.dataframe`)
    - Bei Fehler: `st.error(...)` mit deutscher Fehlermeldung, kein Crash
    - Wenn keine Strategien registriert: `st.info("Keine Strategien registriert")`
  - **Tab "Read-Mode"**: bestehender Code aus Slice 3.3 (Sidebar Strategie+Run-Selector, Plotly, KPIs, Trades)
  - Strukturiertes Logging via `configure_logging("INFO")` zu Beginn
- `quant_trader.backtest.__init__.py` erweitern: exportiert `DashboardRunner`
- Tests: `tests/backtest/test_dashboard_runner.py` (NEU):
  - Happy Path mit Mock-Orchestrator: ruft `orchestrator.run` mit erwarteten Args auf, returnt `BacktestResult`
  - Strategie unbekannt: `UnknownStrategyError` mit `available`-Liste
  - Ticker leer UND universe leer: `InvalidParamsError`
  - Universe-Preset wird zu Ticker-Liste aufgeloest
  - Custom-Ticker wird uppercase genutzt
  - Run-ID wird generiert im Format YYYYMMDDTHHMMSS
  - Cache-Missing wird durchgereicht
  - Strukturiertes Logging: `backtest.dashboard.start` und `backtest.dashboard.complete` Events
  - Validierung start > end wird vom Orchestrator uebernommen (delegation test)
  - mind. 10 Tests, mit `monkeypatch` und `tmp_path`

## Out of Scope (verbindlich)

- Strategie-Vergleichsansicht (Slice 3.6 / US-P3.10)
- Live-Paper-Trading (Phase 5)
- Auto-Run on Tab-Switch / Cancel-Button
- Parameter-Presets / Sweeps
- Editierbare Felder fuer Fill-Mode, Initial-Cash, Granularity
- Multi-Backtest-Batch in einem Run
- Aenderungen an `BacktestEngine`, `MetricsCalculator`, Report-Sub-Package, Orchestrator
- Aenderungen an der CLI

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies.
- Kein `print` in Library-Code (structlog / `st.*` in Script).
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, UI-Strings deutsch (NFR-Ux-1), Logs englisch.
- `DashboardRunner` ist Library-Code ohne Streamlit-Import (Tests laufen ohne UI extra).
- Streamlit-Import in `scripts/backtest_dashboard.py` bleibt `try/except ImportError`.
- Tests muessen deterministic sein, `monkeypatch` fuer Settings-Pfade.

## Mapped NFRs

- NFR-Ux-1: UI-Texte deutsch, klare Fehlermeldungen mit Pfad- und Strategie-Liste.
- NFR-Obs-1: Strukturiertes Logging (`backtest.dashboard.start`, `backtest.dashboard.complete`).
- NFR-Perf-1: <30s fuer 5y Daily (gilt fuer UI-getriggerte Runs ueber Orchestrator).
- NFR-Data-1: Parquet-Cache wird ueber bestehende DataProvider genutzt.

## UML-Referenz

Visualisiert in: `docs/uml/p3-backtest/dashboard.md` (Status: APPROVED, 2026-07-14).

## Done when

- [ ] `src/quant_trader/backtest/dashboard_runner.py` mit `DashboardRunner`.
- [ ] `scripts/backtest_dashboard.py` mit zwei Tabs (Run-Form + Read-Mode), Progress, Fehler-Handling.
- [ ] `quant_trader.backtest.__init__.py` exportiert `DashboardRunner`.
- [ ] Tests in `tests/backtest/test_dashboard_runner.py` (mind. 10 Tests).
- [ ] `make test` gruen.
- [ ] `make lint` gruen.
- [ ] `uv run mypy src` gruen (ohne pre-existing logging.py).
- [ ] Smoke: `uv run python -c "import importlib.util; spec=importlib.util.spec_from_file_location('d','scripts/backtest_dashboard.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('OK')"` laedt das Script ohne Streamlit-Import-Crash.
- [ ] Conventional Commit `feat(p3-backtest): slice 3.5 dashboard run-trigger`.
- [ ] `docs/STATE.md` aktualisiert: Slice 3.5 auf DONE, Tag `p3-backtest/3.5`.

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p3-backtest/backtest.md
cat docs/uml/p3-backtest/dashboard.md
cat docs/prd/p3-backtest/dashboard.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. Vergleichsansicht kommt in 3.6.
- `DashboardRunner` ist Library-Code ohne Streamlit-Import.
- Streamlit-Block im Script mit `try/except ImportError` wrappen.
- Bestehende `BacktestDashboard`-Logik (Read-Mode) nicht ueberschreiben.

Nach dem Coden:
- Conventional Commit mit `feat(p3-backtest): slice 3.5 dashboard run-trigger`.
- Commit-Body: warum `DashboardRunner` separat vom Orchestrator (UI-nahe Validierung
  ohne Orchestrator-DI zu aendern), warum Run-ID via `datetime.now` (UI-Trigger,
  mehrere Runs pro Sekunde unkritisch).