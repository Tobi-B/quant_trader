# PRD: Slice 2.2 - Trend-Strategien (SMA-Cross + Momentum)

Phase:    P2 Strategien
Slice:    2.2 Trend-Strategien
Status:   DRAFT  (wartet auf User-APPROVED)
Author:   opencode
Created:  2026-07-10
Updated:  2026-07-10

## Goal

Zwei klassische Trend-Strategien bereitstellen, die ueber das Strategy-Framework
aus Slice 2.1 instanziiert und in spaeteren Backtests (Phase 3) genutzt werden
koennen:
- **SMA-Cross**: klassischer Crossover (z.B. 20/50) auf einem einzelnen Ticker.
- **Momentum 12-1**: monatliches Cross-Sectional-Ranking ueber ein Universum,
  Top-N-Performer werden gekauft, der Rest verkauft.

## Scope (IN)

- `src/quant_trader/strategies/sma_cross.py`
  - `SmaCrossStrategy(StrategyBase)` mit:
    - ClassVar `name = "sma_cross"`, `version = "1.0.0"`,
      `default_params = {"fast": 20, "slow": 50}`
    - `__init__` von Base erbt default_params-Merge
    - `warmup_bars()` -> `int(self.params["slow"])`
    - `on_bar(bar, portfolio)` -> Rolling-Fenster der `close`-Werte, SMA-Berechnung,
      Crossing-Detection; emittiert `Signal(BUY, "sma_cross_up")` bzw.
      `Signal(SELL, "sma_cross_down")`; sonst leer.
- `src/quant_trader/strategies/momentum.py`
  - `MomentumStrategy(MultiTickerStrategyBase)` mit:
    - ClassVar `name = "momentum"`, `version = "1.0.0"`,
      `default_params = {"lookback_months": 12, "skip_recent_months": 1, "top_n": 10,
                        "rebalance_freq": "monthly"}`
    - `warmup_bars()` -> `lookback_months * 21` (21 Trading-Dage/Monat,
      deterministischer Schätzwert; exakte Kalender-Berechnung in P3)
    - `on_universe_bars(timestamp, bars_by_ticker, portfolio)`:
      - sammelt historische Bars pro Ticker (rolling, in der Instanz gehalten)
      - am Monatsende (per `rebalance_freq`): berechnet 12-1 Monats-Return
        pro Ticker, sortiert absteigend, waehlt Top-N
      - emittiert SELL fuer aktuelle Holdings ausserhalb Top-N
      - emittiert BUY fuer Top-N die nicht im Portfolio sind
      - sonst: leer
- Registrierung beider Klassen via `StrategyLoader.register(...)` - in der
  jeweiligen Modul-Datei (Self-Registration am Ende des Moduls).
- `config/strategies.yaml`: Beispiel-Sections fuer `sma_cross` und `momentum`
  (auskommentiert oder aktiv, default-Periode passt zu US-P2.3/2.4).
- Tests: `tests/strategies/test_sma_cross.py`, `test_momentum.py` mit
  deterministischen Bar-Sequenzen (min. 4 Kategorien):
  - SMA-Cross: warmup, kein crossing, up-crossing, down-crossing, exakte
    Periode-Boundaries
  - Momentum: warmup (kein Lookback voll), kein Top-N-Wechsel, voller Wechsel,
    rebalance_freq nicht-monatlich (z.B. quarterly)

## Out of Scope (verbindlich)

- RSI- und ETF-Rotation-Strategien (Slices 2.3, 2.4).
- Signal-Runner-CLI (`python -m quant_trader.strategies run`) - Slice 2.5.
- Backtest-Engine, P&L, Metriken - Phase 3.
- Konkrete Fill-Logik, Slippage, Kommission - Phase 3.
- Volatility-Adjustierung der Position-Groessen.
- Bond-Alternative fuer 0-Momentum-Perioden (US-P2.4 Out-of-Scope).
- Portfolio-Management (Cash, Equity) - Phase 3, hier nur `PortfolioState`-Stub.
- Monatsende-Detection ueber echte Kalender (z.B. Feiertage) - in P3.

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies (`pandas` ist bereits da; Berechnungen via pure Python
  + `Bar`-Liste, ohne `pandas.Series`-Tricks fuer Lesbarkeit).
- Kein `print`, kein globaler State, kein Wildcard-Import.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, Logs englisch.
- Beide Klassen registrieren sich selbst am Modulende via
  `StrategyLoader.register(...)` - der Loader wird im `__init__.py` der
  `strategies`-Package erzeugt und ueber `loader.register(Cls)` aufgerufen.
- `momentum.py` haelt History als `dict[str, list[Bar]]` in der Instanz (nicht
  als ClassVar - Instanz-State); Max-Groesse per `lookback_months + skip_recent + 1`
  Monate; aelterer Bar wird verworfen.
- `on_universe_bars` darf NICHT annehmen, dass `bars_by_ticker` alle Ticker
  enthaelt; fehlende Ticker werden ignoriert (mit Log-Warning).
- Rebalance-Detection: ueber `timestamp.month`-Wechsel (stateful).
  Initialer State hat `last_rebalance_month = None`; erstes `on_universe_bars`
  im neuen Monat loest Rebalance aus.

## Mapped NFRs

- NFR-Perf-2 (schnelle Berechnung): SMA via einfacher `sum()/n`; Momentum via
  `((close[-1] / close[-(skip+lookback)*21]) - 1)`-Formel; O(n_bars) pro Ticker.
  Keine pandas-Operationen, die zusaetzliche Memory-Kopien verursachen.
- NFR-Ux-1 (klare Fehler): `default_params`-Validierung in `__init__`
  (z.B. `fast < slow`, `lookback_months > skip_recent_months`) mit klarer
  `StrategyError`-Message.
- NFR-Obs-1 (structlog): `MomentumStrategy` loggt `momentum.rebalance` mit
  Top-N-Tickern; `SmaCrossStrategy` loggt nichts (zu haeufig, wuerde Logs
  fluten).

## UML-Referenz

Visualisiert in: `docs/uml/p2-strategies/trend.md` (Status: APPROVED)

## Done when

- [ ] `src/quant_trader/strategies/sma_cross.py` und `momentum.py`
      implementiert.
- [ ] Beide Klassen in `src/quant_trader/strategies/__init__.py` exportiert
      und im dortigen Loader registriert.
- [ ] `config/strategies.yaml` enthaelt Beispiel-Sections fuer beide.
- [ ] Tests: `test_sma_cross.py` (>= 6 Tests), `test_momentum.py`
      (>= 5 Tests) - alle deterministisch und gruen.
- [ ] `make test` gruen (alle 120 + neue Tests).
- [ ] `make lint` gruen.
- [ ] `mypy src/quant_trader/strategies` ohne neue Errors.
- [ ] Conventional Commit(s) `feat(p2-strategies): slice 2.2 trend strategies`.
- [ ] `docs/STATE.md` aktualisiert (Slice 2.2 DONE, Tag `p2-strategies/2.2`
      abgeschlossen).

## Anti-Drift-Reminder

Vor dem Coden:

```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p2-strategies/strategies.md
cat docs/uml/p2-strategies/trend.md
cat docs/prd/p2-strategies/trend.md   # diese Datei
```

Waehrend des Codens:

- Tue **nur** das, was in `Scope (IN)` steht. RSI gehoert in 2.3, ETF-Rotation
  in 2.4, Runner in 2.5.
- Momentum-History-State bleibt in der Instanz, nicht in ClassVar.
- Kein pandas - die Strategien sollen ohne grosse Dep-Kette funktionieren.

Nach dem Coden:

- Conventional Commit(s).
- Commit-Body erklaert: warmup-Bars-Schaetzung (`*21`), fehlende Monatsende-
  Kalender-Logik (out of scope), rebalance_freq-State-Machine-Ansatz.
