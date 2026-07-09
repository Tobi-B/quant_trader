# PRD: Slice 2.3 - Mean-Reversion (RSI)

Phase:    P2 Strategien
Slice:    2.3 Mean-Reversion (RSI)
Status:   DRAFT  (wartet auf User-APPROVED)
Author:   opencode
Created:  2026-07-10
Updated:  2026-07-10

## Goal

Eine klassische Mean-Reversion-Strategie auf Basis des Relative-Strength-Index
(RSI) bereitstellen, die ueber das Strategy-Framework aus Slice 2.1 instanziiert
und in spaeteren Backtests (Phase 3) genutzt werden kann. Signale werden bei
Crossings der RSI-Kurve mit konfigurierbaren Schwellen ausgeloest.

## Scope (IN)

- `src/quant_trader/strategies/rsi_mean_reversion.py`
  - `RsiMeanReversionStrategy(StrategyBase)` mit:
    - ClassVar `name = "rsi_mean_reversion"`, `version = "1.0.0"`,
      `default_params = {"period": 14, "oversold": 30.0, "overbought": 70.0}`
    - `__init__`: validiert `period >= 1` und `0 < oversold < overbought < 100`
    - `warmup_bars()` -> `period + 1` (eine zusaetzliche Bar fuer die erste
      Aenderung)
    - `on_bar(bar, portfolio)`:
      - Rolling-Fenster der `close`-Werte (maxlen=period+1)
      - Berechnet simple-average RSI: `avg_gain = sum(gains)/period`,
        `avg_loss = sum(losses)/period`, `rs = avg_gain/avg_loss`,
        `rsi = 100 - 100/(1+rs)`; `avg_loss == 0` -> `rsi = 100`
      - Crossing-Detection:
        - `prev_rsi >= oversold AND rsi < oversold` -> `Signal(BUY, "rsi_oversold_cross")`
        - `prev_rsi <= overbought AND rsi > overbought` -> `Signal(SELL, "rsi_overbought_cross")`
      - Speichert aktuelles RSI als prev
- Self-Registration: `__init__.py` der `strategies`-Package exportiert
  `RsiMeanReversionStrategy` und registriert sie im `default_loader()`.
- `config/strategies.yaml`: Beispiel-Section `rsi_mean_reversion` mit Defaults.
- Tests: `tests/strategies/test_rsi_mean_reversion.py` mit deterministischen
  Bar-Sequenzen (>= 6 Tests):
  - `warmup_bars()` Korrektheit
  - Default-Parameter
  - Keine Signale waehrend Warmup
  - Keine Signale bei konstantem Preis (RSI=50)
  - BUY bei Crossing unter oversold
  - SELL bei Crossing ueber overbought
  - Invalid period (0) raises
  - Invalid thresholds (oversold >= overbought) raises
  - Signal-Ticker kommt von `self.ticker`

## Out of Scope (verbindlich)

- ETF-Rotation (Slice 2.4).
- Signal-Runner-CLI (Slice 2.5).
- Backtest-Engine, P&L, Metriken (Phase 3).
- Wilder-smoothing RSI (Cutler-/SMA-Variante gewaehlt fuer Klarheit;
  Wilders-Variante kann spaeter als Parameter ergaenzt werden).
- Multi-Timeframe-RSI.
- Divergenz-Erkennung (Preis vs. RSI).
- Konfigurierbare Signalstaerke (Confidence) - US-P2.5 Out-of-Scope.
- Logging auf `on_bar`-Ebene (zu haeufig, wuerde Logs fluten).

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies.
- Kein `print`, kein globaler State.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, Logs englisch.
- RSI-Berechnung via pure Python (kein pandas), deterministisch.
- Crossing-Detection erfordert 2 RSI-Werte (prev + current); erste
  RSI-Berechnung wird nur als `prev` gespeichert (kein Signal).
- `default_params` Validierung in `__init__` mit `StrategyError`.

## Mapped NFRs

- NFR-Perf-2 (schnelle Berechnung): Rolling-Fenster maxlen=period+1;
  Berechnung in O(period) pro Bar, ohne Speicher-Allokationen ausser deque.
- NFR-Ux-1 (klare Fehler): Validierungs-Fehler mit konkreten Werten in der
  Message (z.B. "period muss >= 1 sein (got 0)").

## UML-Referenz

Visualisiert in: `docs/uml/p2-strategies/rsi.md` (Status: APPROVED)

## Done when

- [ ] `src/quant_trader/strategies/rsi_mean_reversion.py` implementiert.
- [ ] `RsiMeanReversionStrategy` in `__init__.py` exportiert + registriert.
- [ ] `config/strategies.yaml` enthaelt Beispiel-Section.
- [ ] Tests `test_rsi_mean_reversion.py` (>= 6) - alle deterministisch gruen.
- [ ] `make test` gruen (alle 142 + neue Tests).
- [ ] `make lint` gruen.
- [ ] `mypy src/quant_trader/strategies` ohne neue Errors.
- [ ] Conventional Commit `feat(p2-strategies): slice 2.3 rsi mean-reversion`.
- [ ] `docs/STATE.md` aktualisiert (Slice 2.3 DONE).

## Anti-Drift-Reminder

- Tue **nur** das, was in `Scope (IN)` steht. ETF-Rotation gehoert in 2.4,
  Runner in 2.5, Backtest in P3.
- Simple-average RSI, nicht Wilder - dokumentiert in Commit-Body.
- Kein Logging auf on_bar (NFR-Obs-1: nur seltene Events loggen).
