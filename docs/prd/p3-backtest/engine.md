# PRD: Slice 3.1 - Backtest Engine Core

Phase:    P3 Backtest-Engine + Reports
Slice:    3.1 Backtest Engine Core
Status:   DRAFT  (wartet auf User-APPROVED; User-Instruction "ja starten" am 2026-07-14 gilt als Approval)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Eine deterministische Backtest-Engine bereitstellen, die registrierte Strategien
(Slice 2.x) auf historische Bars aus dem Parquet-Cache anwendet, Signale zu
Trades konvertiert, ein Portfolio fuehrt (Cash + Positionen) und eine
Equity-Curve sowie Trade-Liste zurueckgibt. Equal-Weight Position-Sizing ist
Teil dieses Slices. Metrics, Report und CLI folgen in 3.2-3.4.

## Scope (IN)

- `quant_trader.backtest` Package:
  - `__init__.py` mit Public-API
- `quant_trader.backtest.types`:
  - `FillMode` (StrEnum: NEXT_OPEN, SAME_CLOSE)
  - `BacktestConfig` (frozen dataclass: initial_cash, fill_mode, sizer)
  - `Fill` (frozen dataclass: ticker, timestamp, price, qty, action, fee=0.0)
  - `PendingFill` (frozen dataclass: signal, execute_on Bar)
  - `Trade` (frozen dataclass: ticker, entry_date, entry_price, exit_date, exit_price, pnl, pnl_pct)
  - `EquitySnapshot` (frozen dataclass: date, equity, cash, positions dict[str,int])
  - `BacktestResult` (frozen dataclass: strategy_name, params, start, end,
    fill_mode, initial_cash, final_equity, trades list[Trade],
    equity_curve list[EquitySnapshot])
- `quant_trader.backtest.errors`:
  - `BacktestError` (Basis)
  - `BacktestConfigError` (z.B. invalid sizer, invalid dates)
- `quant_trader.backtest.sizer`:
  - `PositionSizer` (Protocol) mit `allocate(price, available_cash, n_open_positions) -> SizingResult`
  - `SizingResult` (frozen dataclass: qty int, allocated_cash float, skipped bool)
  - `EqualWeightSizer` (Konkret-Implementierung: 1/n mit Rest als Cash, skipped bei cash<=0)
- `quant_trader.backtest.portfolio`:
  - `Portfolio` (frozen dataclass: cash float, positions dict[str,int])
  - Methoden: `with_cash(delta) -> Portfolio`, `with_position(ticker, delta_shares) -> Portfolio`,
    `equity(prices dict[str,float]) -> float`, `n_open_positions() -> int`
- `quant_trader.backtest.fill`:
  - `FillSimulator` mit `simulate(signal, next_bar, mode) -> Fill`
  - Logik: NEXT_OPEN -> fill_price = next_bar.open; SAME_CLOSE -> fill_price = signal.timestamp bar close
- `quant_trader.backtest.engine`:
  - `BacktestEngine(strategy, bars_by_ticker, config) -> BacktestResult`
  - Iteration single-ticker (StrategyBase.on_bar) und multi-ticker
    (MultiTickerStrategyBase.on_universe_bars)
  - Pending-Fill-Queue: Signale werden zu PendingFill mit execute_on =
    naechste Bar (NEXT_OPEN) bzw. gleiche Bar (SAME_CLOSE)
  - Reihenfolge: bar -> strategy.on_bar -> pending fills ausfuehren ->
    EquitySnapshot
  - BUY: Sizer.allocate(price, cash, n_open_positions) -> Portfolio.open
  - SELL: vorhandene Position full close (verwendet entry_price als Cost-Basis)
  - SELL ohne offene Position: no-op + Warn-Log
  - BUY auf bereits gehaltene Position: no-op (kein Doppelkauf)
  - Strukturiertes Logging: `backtest.start` (strategy, bars_count, mode) und
    `backtest.complete` (duration_ms, trades, final_equity)
  - SELL -> Trade wird geschlossen, in `result.trades` angehaengt
  - `backtest.insufficient_cash` Warn-Log bei Sizer-Skip
- `quant_trader.backtest.__main__.py` ist **nicht** Teil dieses Slices (kommt mit CLI in 3.4)
- Tests:
  - `tests/backtest/test_types.py`
  - `tests/backtest/test_sizer.py` (EqualWeight: 100k/3 -> 33333.33, 0 cash -> skipped, 1 ticker -> 100%)
  - `tests/backtest/test_portfolio.py` (with_cash, with_position, equity, n_open)
  - `tests/backtest/test_fill.py` (NEXT_OPEN vs SAME_CLOSE)
  - `tests/backtest/test_engine.py`:
    - happy path single-ticker (BUY -> SELL -> Trade)
    - happy path multi-ticker (etf_rotation smoke)
    - re-buy no-op
    - sell-without-position no-op + warn-log
    - insufficient_cash skip + warn-log
    - equity_curve length matches bar count
    - single-ticker ohne Signale (0 trades)
    - backtest.start + backtest.complete logs

## Out of Scope (verbindlich)

- Metrics (Sharpe, CAGR, MDD, Win-Rate, Exposure) - Slice 3.2
- Report (ConsoleFormatter, Plotly HTML, JSON, Streamlit) - Slice 3.3
- Backtest-CLI - Slice 3.4
- Interaktives Dashboard - Slice 3.5
- Commission, Slippage, Stop-Loss, Limit-Orders (immer Market) - Phase 4 risk
- Multi-Stage / Partial-Fills (immer full fill)
- Leverage / Margin / Short-Selling (immer Long-only)
- Persistenz von `BacktestResult` (kommt mit Report in 3.3)

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies.
- Kein `print`, kein globaler State, kein Wildcard-Import.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, Logs englisch.
- `BacktestResult` ist **immutable** (frozen dataclass). Engine baut das
  Result-Objekt am Ende; waehrend der Iteration werden nur lokale
  Intermediate-States gehalten.
- `bars_by_ticker` ist `dict[str, list[Bar]]` mit chronologisch sortierten Bars.
  Engine sortiert defensiv (idempotent), wirft `BacktestConfigError` bei
  leerem Dict oder leerer Bar-Liste.
- Bars muessen `Bar.adjusted_close` enthalten (Adj. Close fuer Equity-Berechnung
  bei Corporate Actions, NFR-Data-2).
- Performance-Budget: 5 Jahre Daily < 30s (NFR-Perf-1). Engine vermeidet
  teure Kopien; nutzt list comprehensions statt pandas.
- Test-Daten: synthetische Bar-Sequenzen (siehe bestehende Tests fuer Pattern).

## Mapped NFRs

- NFR-Perf-1 (<30s fuer 5y Daily): pure-Python, keine pandas-Operationen
  im Hot-Path, list comprehensions.
- NFR-Obs-1 (structlog): `backtest.start`, `backtest.complete`,
  `backtest.insufficient_cash`, `backtest.sell_no_position` mit Strategy-
  und Ticker-Kontext.
- NFR-Data-1 (Parquet-Cache): Engine liest `list[Bar]` aus dem Cache
  (nicht selbst); ParquetCache ist Input-Layer.
- NFR-Data-2 (Adj. Close): `equity()` nutzt `bar.adjusted_close`.

## UML-Referenz

Visualisiert in: `docs/uml/p3-backtest/engine.md` (Status: wird auf
APPROVED gesetzt mit diesem Slice).

## Done when

- [ ] `src/quant_trader/backtest/` enthaelt `__init__.py`, `types.py`,
      `errors.py`, `sizer.py`, `portfolio.py`, `fill.py`, `engine.py`
      gemaess Scope.
- [ ] Tests in `tests/backtest/` decken alle Acceptance-Criteria ab.
- [ ] `make test` gruen (alle 185 alten + neuen Tests).
- [ ] `make lint` gruen (ruff check + format --check).
- [ ] `uv run mypy` gruen (--strict).
- [ ] Conventional Commit `feat(p3-backtest): slice 3.1 backtest engine core`.
- [ ] `docs/STATE.md` aktualisiert: Slice 3.1 auf DONE, Tag
      `p3-backtest/3.1` setzen.
- [ ] Out-of-Scope-Items in zukuenftige PRD/Story verschoben (falls relevant).

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p3-backtest/backtest.md
cat docs/uml/p3-backtest/engine.md
cat docs/prd/p3-backtest/engine.md   # diese Datei
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. Metrics, Report, CLI gehoeren
  in 3.2-3.4.
- Wenn etwas Off-Scope auftaucht: STOP, dokumentiere in Commit-Body oder
  STATE.md, frage Nutzer.
- Wenn Tests fehlschlagen: **erst** Tests verstehen, dann Code fixen.

Nach dem Coden:
- Conventional Commit mit `feat(p3-backtest): slice 3.1 backtest engine core`.
- Commit-Body enthaelt: warum Engine ohne pandas-Operationen, was verworfen
  wurde (z.B. explizite State-Machine-Klasse zugunsten einer
  Frozen-Dataclass-Pipeline).
