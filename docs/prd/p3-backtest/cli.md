# PRD: Slice 3.4 - Backtest CLI

Phase:    P3 Backtest-Engine + Reports
Slice:    3.4 Backtest CLI
Status:   DRAFT  (wartet auf User-APPROVED; User-Instruction am 2026-07-14 gilt als Approval)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Einen Backtest reproduzierbar per CLI-Aufruf starten koennen
(`python -m quant_trader.backtest run ...`) und bestehende Runs einsehen
(`... list`). Die CLI kombiniert die vorhandene Backtest-Engine (3.1), die
Metriken (3.2) und den Report (3.3) zu einem End-to-End-Workflow, der
zusaetzlich eine `run_id` vergibt, strukturierte Logs schreibt und klare
deutsche Fehlermeldungen liefert.

## Scope (IN)

- `src/quant_trader/backtest/errors.py` erweitern:
  - `UnknownStrategyError(BacktestError)` mit `name` und `available` Attributen
  - `CacheMissingError(BacktestError)` mit `ticker` und `path` Attributen
  - `InvalidParamsError(BacktestError)`
  - `BacktestError` und `BacktestConfigError` bleiben unveraendert
- `src/quant_trader/backtest/orchestrator.py` (NEU):
  - `BacktestOrchestrator(cache, loader, report_builder=None, reports_dir=Path("./reports"))`
  - `run(run_id, strategy_name, ticker="", universe=None, start, end, granularity=DAILY, fill_mode=NEXT_OPEN, initial_cash=100_000.0, write_report=True) -> BacktestResult`
  - Logik:
    1. Validierung: `ticker` XOR `universe/params.universe` (Single braucht ticker, Multi braucht universe)
    2. Strategie laden via `loader.load(name, ticker=ticker)`
    3. Bars laden (Single: ein Ticker, Multi: Liste aus Preset oder params)
    4. Bei `FileNotFoundError` -> `CacheMissingError` (deutsche Message mit Pfad)
    5. `BacktestConfig` + `BacktestEngine.run` -> `BacktestResult`
    6. Optional: `ReportBuilder.build(...)` wenn `write_report=True`
    7. Strukturiertes Logging: `backtest.orchestrator.start`, `backtest.orchestrator.complete`, `backtest.cache_missing`, `backtest.unknown_strategy`
  - Raises: `UnknownStrategyError`, `CacheMissingError`, `InvalidParamsError`, `BacktestError` (von Engine)
- `src/quant_trader/backtest/cli.py` (NEU):
  - `build_parser() -> ArgumentParser` mit Subcommands:
    - `run`: `--strategy` (required), `--ticker` (default ""), `--universe` (default None), `--start` (required, YYYY-MM-DD), `--end` (required), `--granularity` (default "daily", choices daily/60m/15m), `--fill-mode` (default "next_open", choices next_open/same_close), `--initial-cash` (default 100000, type float), `--no-report` (store_true)
    - `list`: ohne Argumente
  - `main(argv=None) -> int`:
    - `configure_logging("INFO")` zu Beginn
    - parsed args, ruft Orchestrator fuer `run`, oder `ReportLoader` fuer `list`
    - druckt ConsoleFormatter Output (run) bzw. formatierte Tabelle (list)
    - Exit 0 bei Erfolg, Exit 1 bei Fehler
    - Deutsche Fehlermeldungen auf stderr via `log.error(...)`
- `src/quant_trader/backtest/__main__.py` (NEU): ruft `cli.main()`
- `src/quant_trader/backtest/__init__.py` erweitern: exportiert `BacktestOrchestrator`, `UnknownStrategyError`, `CacheMissingError`, `InvalidParamsError`
- `scripts/run_backtest.py` aktualisieren: leitet auf `python -m quant_trader.backtest` (oder ruft `cli.main()`)
- Tests: `tests/backtest/test_cli.py` (NEU):
  - Parser-Structure (run braucht --strategy/--start/--end, defaults, choices, --no-report flag)
  - `list` Subcommand ohne Args
  - Happy Path: gemockter Cache + Loader, Report wird geschrieben, Console ausgegeben, Exit 0
  - `--no-report`: keine Files geschrieben
  - `--fill-mode same_close`: nutzt `FillMode.SAME_CLOSE`
  - `--initial-cash 50000`: nutzt custom cash
  - unbekannte Strategie: Exit 1, deutsche Fehlermeldung
  - fehlender Cache: Exit 1, deutsche Fehlermeldung
  - single-ticker ohne `--ticker`: Exit 1 (Strategy-Validation)
  - multi-ticker ohne universe: Exit 1
  - `list` mit Reports: formatierte Tabelle
  - `list` ohne Reports: Hinweis "Noch keine Backtests"
  - mind. 12-15 Tests mit `monkeypatch` fuer Settings-Pfade

## Out of Scope (verbindlich)

- Streamlit-Trigger (Slice 3.5)
- Aenderungen an `BacktestEngine`, `MetricsCalculator`, Report-Sub-Package
- Multi-Backtest-Batch in einem CLI-Call
- Scheduler/Cron-Integration
- Live-Trading-Trigger
- BacktestEngine.write_report (es gibt das nicht) - Orchestrator ruft ReportBuilder

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies.
- Kein `print` im Library-Code (structlog).
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, CLI-Strings deutsch (NFR-Ux-1), Logs englisch.
- Orchestrator akzeptiert `cache` und `loader` als Dependencies (DI-Pattern) - keine Singletons.
- ConsoleFormatter bleibt unveraendert (deterministisch).
- Tests muessen deterministic sein, `monkeypatch` fuer `DATA_DIR`/`STRATEGIES_CONFIG_PATH`/`UNIVERSE_PRESETS_PATH`.

## Mapped NFRs

- NFR-Ux-1: CLI-Texte deutsch, klare Fehlermeldungen mit Pfad- und Strategie-Liste.
- NFR-Obs-1: Strukturiertes Logging (structlog Events `backtest.orchestrator.start`, `backtest.orchestrator.complete`, `backtest.cache_missing`, `backtest.unknown_strategy`).

## UML-Referenz

Visualisiert in: `docs/uml/p3-backtest/cli.md` (Status: APPROVED, 2026-07-14).

## Done when

- [ ] `src/quant_trader/backtest/errors.py` mit erweiterter Hierarchie.
- [ ] `src/quant_trader/backtest/orchestrator.py` mit `BacktestOrchestrator`.
- [ ] `src/quant_trader/backtest/cli.py` mit `build_parser` + `main`.
- [ ] `src/quant_trader/backtest/__main__.py` Entry-Point.
- [ ] `src/quant_trader/backtest/__init__.py` exportiert neue Symbole.
- [ ] `scripts/run_backtest.py` ruft `cli.main()`.
- [ ] Tests in `tests/backtest/test_cli.py` (mind. 12-15 Tests).
- [ ] `make test` gruen.
- [ ] `make lint` gruen.
- [ ] `uv run mypy` gruen (ohne pre-existing logging.py).
- [ ] Conventional Commit `feat(p3-backtest): slice 3.4 backtest cli`.
- [ ] `docs/STATE.md` aktualisiert: Slice 3.4 auf DONE, Tag `p3-backtest/3.4`.

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p3-backtest/backtest.md
cat docs/uml/p3-backtest/cli.md
cat docs/prd/p3-backtest/cli.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. Run-Trigger im Dashboard kommt in 3.5.
- `BacktestEngine` / `MetricsCalculator` / `Report` Packages nicht anfassen.
- Tests muessen `monkeypatch` fuer Settings nutzen (Pattern in `tests/strategies/test_runner.py`).

Nach dem Coden:
- Conventional Commit mit `feat(p3-backtest): slice 3.4 backtest cli`.
- Commit-Body: warum DI-Pattern fuer Orchestrator (Testbarkeit), warum Error-Hierarchie mit `name`/`available` Attributen.
