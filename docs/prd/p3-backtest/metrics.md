# PRD: Slice 3.2 - Metrics

Phase:    P3 Backtest-Engine + Reports
Slice:    3.2 Metrics
Status:   DRAFT  (User "ja starten" gilt als implizite Approval; UML auf APPROVED setzen)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Aus einem abgeschlossenen `BacktestResult` die wichtigsten Performance-
Kennzahlen ableiten, damit der Trader die Strategie schnell bewerten kann
(US-P3.3). Output: ein `Metrics`-Snapshot mit Total Return, CAGR, Sharpe
Ratio, Max Drawdown, Win-Rate, Trade-Count und Exposure.

## Scope (IN)

- `quant_trader.backtest.metrics`:
  - `Metrics` (frozen dataclass):
    - `total_return_pct: float`
    - `cagr_pct: float`
    - `sharpe_ratio: float | None` (None bei <2 Returns, std=0 oder Empty-Run)
    - `max_drawdown_pct: float` (immer >= 0, 0 bei 0/1 Snapshots)
    - `win_rate_pct: float | None` (None bei <2 Trades)
    - `n_trades: int`
    - `exposure_pct: float` (0-100, % der Snapshots mit Position)
  - `MetricsCalculator` mit `calculate(result: BacktestResult) -> Metrics`
  - `EquityCurveStats` (Helper):
    - `compute_returns(equity_curve) -> list[float]` (einfache tagesuebergreifende
      Returns, erstes Element 0)
    - `cagr_pct(equity_curve, initial_cash) -> float` ((end/start)^(252/years) - 1) * 100
    - `sharpe(returns) -> float | None` (mean/std * sqrt(252), rf=0; None bei
      len<2 oder std==0)
    - `max_drawdown_pct(equity_curve) -> float` (groesster Peak-zu-Tal-Verlust in %)
    - `exposure_pct(snapshots) -> float` (Anteil Snapshots mit positions != {})
  - `TradeStats` (Helper):
    - `win_rate_pct(trades) -> float | None` (trades mit pnl>0 / total * 100; None
      bei <2 Trades)
- Tests: `tests/backtest/test_metrics.py` (mind. 18 Tests):
  - Total Return simple up/down/flat
  - CAGR simple 1y/2y/flat
  - Sharpe empty / single / flat (std=0) / normal
  - Max Drawdown simple / monoton steigend (0) / single point (0) / V-Form
  - Win-Rate empty / 1 trade (None) / 2 trades (one win) / 5 trades
  - Exposure empty / all flat / all invested / mixed
  - Edge: 0 snapshots, 1 snapshot, 0 trades
  - Empty-Run integration: alle Metriken ausser n_trades = 0 oder None

## Out of Scope (verbindlich)

- Sortino, Calmar, Information Ratio (US-P3.3 Out-of-Scope; spaeter)
- Trade-PnL-Distribution (Histogramme)
- Risk-adjusted Benchmarks (Alpha, Beta vs. Index)
- Drawdown-Chart (kommt mit Report in 3.3)
- Mehrere Per-Period-Granularitaeten (annualisiert nur 252 Tage)
- Currency-Conversion (alles in USD, gleiche Currency wie Result)

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies (math, statistics oder stdlib reicht).
- Kein `print`, kein globaler State.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch.
- Annualisierungs-Konstante: `TRADING_DAYS_PER_YEAR = 252`.
- Bei `n_trades < 2` werden `sharpe_ratio` und `win_rate_pct` auf `None` gesetzt.
- Bei `n_trades == 0` (Empty-Run) ist `sharpe_ratio` immer `None`, `win_rate_pct`
  immer `None`. Andere Metriken (total_return_pct, cagr_pct, mdd, exposure)
  erhalten sinnvolle Default-Werte (0.0) und sind damit von "strategie hat
  0% Rendite" nicht unterscheidbar - das ist akzeptabel fuer US-P3.3.
- Returns in Prozent: alle `*_pct`-Felder sind in Prozent (0-100), nicht als
  Dezimalbruch.

## Mapped NFRs

- NFR-Perf-1 (<30s fuer 5y Daily): pure-Python-Operationen, O(n) ueber
  equity_curve.
- NFR-Data-2 (Adj. Close): equity_curve nutzt `EquitySnapshot.equity`, das
  im Engine aus `bar.adjusted_close` berechnet wurde.

## UML-Referenz

Visualisiert in: `docs/uml/p3-backtest/metrics.md` (Status: wird auf
APPROVED gesetzt mit diesem Slice).

## Done when

- [ ] `src/quant_trader/backtest/metrics.py` mit `Metrics`,
      `MetricsCalculator`, `EquityCurveStats`, `TradeStats` gemaess Scope.
- [ ] `src/quant_trader/backtest/__init__.py` exportiert `Metrics` und
      `MetricsCalculator`.
- [ ] Tests in `tests/backtest/test_metrics.py` decken Edge-Cases ab.
- [ ] `make test` gruen (alle 227 alten + neuen Tests).
- [ ] `make lint` gruen.
- [ ] `uv run mypy` gruen (--strict, ohne pre-existing logging.py).
- [ ] Conventional Commit `feat(p3-backtest): slice 3.2 metrics`.
- [ ] `docs/STATE.md` aktualisiert: Slice 3.2 auf DONE, Tag
      `p3-backtest/3.2` setzen.

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p3-backtest/backtest.md
cat docs/uml/p3-backtest/metrics.md
cat docs/prd/p3-backtest/metrics.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. Sortino, Calmar, IR
  gehoeren nicht in diesen Slice.
- Wenn etwas Off-Scope auftaucht: STOP, dokumentiere, frage Nutzer.

Nach dem Coden:
- Conventional Commit `feat(p3-backtest): slice 3.2 metrics`.
- Commit-Body enthaelt: warum simple O(n)-Implementierung (Performance
  NFR-Perf-1), was verworfen wurde (z.B. pandas-Series zugunsten von
  stdlib-Listen).
