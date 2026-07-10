# PRD: Slice 2.4 - ETF-Rotation (Top-N Momentum)

Phase:    P2 Strategien
Slice:    2.4 ETF-Rotation
Status:   DRAFT  (wartet auf User-APPROVED)
Author:   opencode
Created:  2026-07-10
Updated:  2026-07-10

## Goal

Eine ETF-Rotation-Strategie bereitstellen, die am Monatsende die
Top-N-ETFs nach 6-Monats-Momentum aus einem Universum auswaehlt und
gleichgewichtet in diese allokiert; bei negativer-Performance aller
ETFs wird vollstaendig liquidiert (Cash-Anteil). Die Strategie nutzt
das `MultiTickerStrategyBase`-Interface aus Slice 2.1 (US-P2.6) und
wird ueber die `StrategyLoader`-Registry instanziiert - sodass sie
in Backtests (Phase 3) ohne weitere Code-Aenderung einsetzbar ist.

## Scope (IN)

- `src/quant_trader/strategies/etf_rotation.py`
  - `EtfRotationStrategy(MultiTickerStrategyBase)` mit:
    - ClassVar `name = "etf_rotation"`, `version = "1.0.0"`,
      `default_params = {"universe": [...], "top_n": 2, "lookback_months": 6, "rebalance_freq": "monthly"}`
    - `__init__`: validiert `top_n >= 1`, `lookback_months >= 1`,
      `rebalance_freq == "monthly"` (analog zu `MomentumStrategy`),
      `len(universe) >= top_n`; alles ueber `StrategyError`
    - `warmup_bars()` -> `lookback_months * 21` (Trading-Tage pro Monat)
    - `on_universe_bars(date, bars_by_ticker, portfolio)`:
      - Rolling-History `dict[ticker, deque[Bar]]` mit maxlen = Lookback-Bars
      - Erstbefuellung + Tages-Append; ein Tag pro `on_universe_bars`-Call
      - **Warmup-Gate**: solange fuer *keinen* ETF
        `lookback_months * 21` Bars vorliegen -> `[]`
      - **Rebalance-Trigger**: erste Bar in neuem `(year, month)` -> rebalance
      - **Lookback-Return** fuer jeden ETF mit ausreichender Historie:
        `return = closes[-1] / closes[-lookback_bars] - 1.0`;
        `closes[0]` <= 0 -> ETF wird uebersprungen
      - **No-positive-Branch**: wenn keiner der ETFs `return > 0` hat:
        `SELL` fuer alle aktuell gehaltenen Positionen (Reason:
        `"etf_rotation_defensive_cash"`)
      - **Top-N-Branch**: `top_n_set = {ticker fuer top-N Returns}`;
        fuer jede aktuell gehaltene Position, die nicht in `top_n_set`:
        `SELL(reason="etf_rotation_dropped_from_top_n")`;
        fuer jeden ETF in `top_n_set`, der nicht gehalten wird:
        `BUY(reason="etf_rotation_entered_top_n")`
      - Nach Rebalance: `current_holdings = portfolio.positions.keys()` als
        "state to emit SELLs from next time"
      - Loggt `etf_rotation.rebalance` (level=info) mit Top-N und
        Signal-Anzahl; `etf_rotation.defensive_cash` bei Vollliquidation
- Self-Registration: `__init__.py` der `strategies`-Package exportiert
  `EtfRotationStrategy` und registriert sie im `default_loader()`.
- `config/strategies.yaml`: Beispiel-Section `etf_rotation` mit Defaults
  (z.B. SPY, AGG, TLT, IEF als Mini-Universum).
- Tests: `tests/strategies/test_etf_rotation.py` mit deterministischen
  Bar-Sequenzen (>= 8 Tests):
  - `warmup_bars()` Korrektheit (default 6*21, mit Param 3*21)
  - Default-Parameter
  - Validierung: `top_n=0` raises; `lookback_months=0` raises;
    `rebalance_freq="weekly"` raises; `len(universe) < top_n` raises
  - Warmup: in den ersten `lookback_months` Monaten keine Signale
  - Erste Rebalance nach Warmup: Top-N ETFs -> BUY; Rest -> kein Signal
  - SELL wenn Halter aus Top-N faellt (mit gesetztem `portfolio.positions`)
  - Defensive Cash: wenn kein ETF positive 6-Monats-Performance hat,
    werden alle Holdings liquidiert (SELL fuer jeden gehaltenen ETF)
  - Keine Doppel-Signale im selben Monat (zweiter Aufruf mit gleichem
    `(year, month)` -> `[]`)
  - Log-Event `etf_rotation.rebalance` bei BUY-/SELL-Emission
  - Strategy wird via `StrategyLoader` aus `config/strategies.yaml` geladen

## Out of Scope (verbindlich)

- Bond-Hedge / 60-40-Mischform (US-P2.6 Out-of-Scope).
- Volatility-adjustierte Positions-Groessen.
- Signal-Runner-CLI (Slice 2.5) - Strategie ist in Slice 2.5 trotzdem
  smoke-testbar via `python -m quant_trader.strategies run`.
- Backtest-Engine, P&L, Equity-Curve (Phase 3).
- Weighting jenseits 1/N (Risk-Parity, inverse Vol, etc.).
- Live-Reload von Universe-Listen (YAML wird einmal beim Start geladen).
- Multi-Timeframe-Rebalance (daily/weekly).
- Persistenz der Rotation-History (Journal kommt in Phase 5).

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies.
- Kein `print`, kein globaler State, kein Wildcard-Import.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, CLI-Strings deutsch, Logs englisch.
- Rebalance-Logik analog zu `MomentumStrategy` (`_TRADING_DAYS_PER_MONTH = 21`,
  `_rebalance_key(timestamp) == (year, month)`).
- Kein `pandas`: Rolling-History in `collections.deque(maxlen=...)`.
- Validierungs-Fehler mit konkreten Werten in der Message
  (z.B. "top_n (3) muss <= len(universe) (2) sein").
- `_current_holdings` wird *nach* jedem Rebalance aus `portfolio.positions`
  uebernommen (Trading-Engine faellt erst zurueck, dann Portfolio-Snapshot);
  in Slice 2.4 ist `PortfolioState` noch ein Stub - der Test setzt
  `positions={"SPY": 1}` manuell, um den Verkettungs-Pfad zu verifizieren.

## Mapped NFRs

- NFR-Perf-2 (schnelle Berechnung): O(lookback) pro ETF pro Rebalance,
  Monats-Frequenz -> 12 Rebalances/Jahr; alles in pure Python mit `deque`.
- NFR-Ux-1 (klare Fehler): jede Validierungs-Verletzung wirft `StrategyError`
  mit konkreten Werten (`top_n`, `len(universe)` etc.).
- NFR-Obs-1 (structlog): Rebalance-Event einmal pro Monat (selten), kein
  Bar-Level-Logging.

## UML-Referenz

Visualisiert in: `docs/uml/p2-strategies/rotation.md` (Status: APPROVED)

## Done when

- [ ] `src/quant_trader/strategies/etf_rotation.py` implementiert.
- [ ] `EtfRotationStrategy` in `__init__.py` exportiert + registriert.
- [ ] `config/strategies.yaml` enthaelt Beispiel-Section `etf_rotation`.
- [ ] Tests `test_etf_rotation.py` (>= 8) - alle deterministisch gruen.
- [ ] `make test` gruen (153 vorher + neue Tests).
- [ ] `make lint` gruen.
- [ ] `mypy src/quant_trader/strategies` ohne neue Errors.
- [ ] Conventional Commit `feat(p2-strategies): slice 2.4 etf-rotation`.
- [ ] `docs/STATE.md` aktualisiert (Slice 2.4 DONE).

## Anti-Drift-Reminder

- Tue **nur** das, was in `Scope (IN)` steht. Bond-Hedge / Vol-Adjustment
  sind explizit OOS und gehoeren in eine spaetere Phase.
- Cross-Sectional-Return ist *pro ETF* (closes[t-lookback] -> closes[t]),
  nicht peer-normalisiert.
- Reihenfolge der Signale: erst `SELL` fuer gedroppte Halter, dann `BUY`
  fuer neue Top-N (deterministisch fuer Tests).
- Verifikation: vor Commit `make test` + `make lint`.
