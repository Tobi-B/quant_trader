# PRD: Slice 2.5 - Signal-Runner CLI

Phase:    P2 Strategien
Slice:    2.5 Signal-Runner-CLI
Status:   DRAFT (wartet auf User-APPROVED)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Eine Thin-CLI bereitstellen, mit der ein Trader eine registrierte Strategie
auf historische Bars aus dem Parquet-Cache anwenden und die resultierenden
Signale als Tabelle auf stdout ausgeben kann, ohne den vollen Backtest
(Phase 3) zu benoetigen. Dient als schneller Smoke-Test der Strategien
aus Slice 2.1 bis 2.4 und als Vorbereitung fuer die Engine-Kopplung.

## Scope (IN)

- `src/quant_trader/strategies/runner.py`
  - `SignalFormatter`: formatiert `list[Signal]` als fixed-width Tabelle
    mit Headern `TIMESTAMP | TICKER | ACTION | REASON`. `format_signals(signals, limit)` -> `str`.
    Wenn `len(signals) > limit`: ein `(... N more)`-Footer wird angehaengt.
  - `SignalRunner`: orchestriert Cache-Read + Strategy-Iteration.
    - `__init__(cache, loader)` mit `ParquetCache` und `StrategyLoader`
    - `run(strategy_name, *, ticker, universe, start, end, granularity, limit)` -> `list[Signal]`
    - Erkennt automatisch `StrategyBase` vs `MultiTickerStrategyBase`
      via `isinstance`.
    - Single-Ticker: `cache.read(ticker, granularity, start, end)` ->
      chronologische Iteration -> `strategy.on_bar(bar, portfolio)`.
    - Multi-Ticker:
      - Resolved Ticker-Liste: aus `--universe` Preset, sonst aus
        `strategy.params["universe"]` (z.B. `etf_rotation`).
      - `cache.read(ticker, ...)` fuer jeden Ticker.
      - Bars nach `timestamp.date()` gruppieren (gleicher Trading-Tag
        pro Ticker).
      - Pro Datum: `strategy.on_universe_bars(ts, bars_by_ticker, portfolio)`.
    - Loggt `signal_runner.start` und `signal_runner.summary`.
  - `run_cli(argv)` -> `int`: baut Parser, ruft Runner, printed Tabelle.
    - Exit 0 bei Erfolg, 1 bei `UnknownStrategyError`, `StrategyConfigError`,
      `FileNotFoundError` (Cache fehlt), `PresetNotFoundError`.
- `src/quant_trader/strategies/cli.py`: schlanker Wrapper, der den
  `StrategyLoader` aus `default_loader()` baut und `SignalRunner` startet.
- `src/quant_trader/strategies/__main__.py`: Entry-Point fuer
  `python -m quant_trader.strategies run ...`.
- `src/quant_trader/strategies/__init__.py`: exportiert `SignalFormatter`,
  `SignalRunner`; registriert sie im public API.
- `tests/strategies/test_runner.py`:
  - `SignalFormatter.format_signals` mit 0, 1, vielen Signalen
  - `SignalFormatter` respektiert `limit` und fuegt Footer an
  - `SignalRunner.run` single-ticker happy path mit Stub-Strategy
  - `SignalRunner.run` multi-ticker happy path mit Stub-Strategy
  - `SignalRunner.run` wirft `FileNotFoundError` bei fehlendem Cache
  - `SignalRunner.run` wirft `UnknownStrategyError` bei unbekanntem Namen
  - CLI: `run --strategy X` mit fehlendem Cache -> Exit 1
  - CLI: `run --strategy unknown` -> Exit 1
  - CLI: argparse `build_parser()` Struktur-Tests
- `docs/STATE.md`: Slice 2.5 als IN_PROGRESS / DONE markieren.

## Out of Scope (verbindlich)

- Backtest-Ausfuehrung mit P&L, Equity-Curve (Phase 3).
- Live-Trading via IBKR (Phase 5).
- Signal-Persistenz (SQLite-Journal kommt in Phase 5).
- Plotly-Charts (gehoert zum Reporting in Phase 3).
- Multi-Timeframe-Strategien (1 Strategie == 1 Granularitaet pro Run).
- Resume / Append von Cache (Runner liest nur).
- Reload der YAML mid-run.
- Bond-Hedge / Vol-Adjustment (Slice 2.4 Out-of-Scope, gilt weiterhin).
- Backtest-Runner-Skript `scripts/run_backtest.py` (Phase 3).

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies (`pyarrow`, `pandas`, `structlog` sind vorhanden).
- Kein `print`, kein globaler State, kein Wildcard-Import.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, CLI-Strings deutsch, Logs englisch.
- Kein `pandas` im Runner selbst: Bars werden aus `list[Bar]` sortiert nach
  `timestamp`; Gruppierung ueber `collections.defaultdict` mit `bar.timestamp.date()`.
- Formatter liefert deterministic Output (fixed-width Spalten) -> testbar.
- CLI-Rueckgabe-Werte:
  - 0 bei Erfolg (auch wenn 0 Signale)
  - 1 bei Fehler (Cache fehlt, unbekannte Strategie, falsches Universe).
- Log-Events: `signal_runner.start(strategy, tickers, bars)`,
  `signal_runner.summary(strategy, signals, days)`; kein Bar-Level-Logging
  (Performance).
- Limit default 100, hart codiert als Konstante in `cli.py`.

## Mapped NFRs

- NFR-Obs-1 (structlog): `signal_runner.start` + `summary` (kein Bar-Noise).
- NFR-Ux-1 (klare Fehler): `UnknownStrategyError` listet verfuegbare Namen
  (vom Loader), `FileNotFoundError` nennt Pfad + Ticker.
- NFR-Data-1 (Cache-Pflicht): Runner liest ausschliesslich aus
  `ParquetCache.read()`, ruft niemals Provider direkt.
- NFR-Perf-2 (schnelle Berechnung): O(bars + signals); kein pd im Hot-Path.

## UML-Referenz

Visualisiert in: `docs/uml/p2-strategies/runner.md` (Status: APPROVED)

## Done when

- [ ] `src/quant_trader/strategies/runner.py` implementiert (Formatter + Runner).
- [ ] `src/quant_trader/strategies/cli.py` und `__main__.py` implementiert.
- [ ] `SignalRunner` und `SignalFormatter` in `__init__.py` exportiert.
- [ ] Tests `test_runner.py` (>= 8) - alle deterministisch gruen.
- [ ] `python -m quant_trader.strategies run --strategy sma_cross --ticker SPY`
      liefert Tabelle (manueller Smoke in `make smoke`).
- [ ] `make test` gruen (168 vorher + neue Tests).
- [ ] `make lint` gruen.
- [ ] `mypy src/quant_trader/strategies` ohne neue Errors.
- [ ] Conventional Commit `feat(p2-strategies): slice 2.5 signal-runner`.
- [ ] `docs/STATE.md` aktualisiert (Slice 2.5 DONE).

## Anti-Drift-Reminder

- Tue **nur** das, was in `Scope (IN)` steht. Phase 3 (Backtest-Engine,
  P&L, Reports) bleibt explizit OOS.
- Formatter nutzt `str.ljust(...)` / `str.rjust(...)`; **keine** `tabulate`-
  Dependency.
- Multi-Ticker-Runner setzt voraus, dass alle Ticker dieselbe Bar-Anzahl
  und gleiche Daten haben (Trading-Tag-Alignment) - das ist Standard fuer
  Universe-Strategien und wird nicht validiert (kommt mit Phase 3).
- Single-Ticker-Runner lehnt `--universe` still ab, wenn Strategie eine
  `StrategyBase` ist (oder gibt klare Fehlermeldung aus, falls beide
  Argumente gegeben sind).