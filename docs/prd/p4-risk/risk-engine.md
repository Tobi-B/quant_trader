# PRD: Slice 4.1 - Risk-Engine (Commission + Slippage + Stop-Loss)

Phase:    P4 Risk Management
Slice:    4.1 Risk-Engine (1 grosser Slice, Commission + Slippage + Stop-Loss)
Status:   DRAFT  (User "weiter mit naechstem slice" gilt als implizite Approval; UML auf APPROVED setzen)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Den BacktestEngine (Slice 3.1) um realistische Kosten (Commission,
Slippage) und ein Downside-Limit (Stop-Loss) erweitern, damit
Netto-Returns realitaetsnah sind und der Trader Downside-Szenarien
analysieren kann. Defaults sind "kostenfrei" und "kein Stop-Loss",
damit die 355 bestehenden Tests unveraendert gruen bleiben.

## Scope (IN)

- `src/quant_trader/backtest/types.py` (aendern):
  - `BacktestConfig` (frozen): neue Felder mit Defaults
    - `commission_per_trade: float = 0.0`
    - `commission_per_share: float = 0.0`
    - `slippage_pct: float = 0.0`
    - `stop_loss_pct: float | None = None`
- `src/quant_trader/backtest/fill.py` (aendern):
  - `FillSimulator` bekommt `slippage_pct: float = 0.0` Parameter
  - `simulate()` wendet Slippage auf den Fill-Preis an:
    - BUY: `price = open_or_close * (1 + slippage_pct/100)`
    - SELL: `price = open_or_close * (1 - slippage_pct/100)`
  - `resolve(pending)` nutzt `self._slippage_pct` fuer die Berechnung
- `src/quant_trader/backtest/engine.py` (aendern):
  - `BacktestEngine.__init__`: nimmt `commission_*`, `slippage_pct`,
    `stop_loss_pct` aus `config` und reicht `slippage_pct` an
    `FillSimulator` weiter
  - `_run_single` / `_run_multi`: rufe `_check_stop_losses(bar,
    portfolio, open_positions, pending, trades, bars_for_ticker)`
    **vor** `strategy.on_bar(bar, ...)`
  - `_check_stop_losses`: pro offene Position: wenn Bar-Open <
    entry_price * (1 - stop_loss_pct/100), enqueue SELL-Signal mit
    Marker `reason="stop_loss"` als internes `Signal` (Action.SELL,
    reason="stop_loss")
  - `_apply_fill`: bei BUY: `cash -= (qty * price + commission)`;
    bei SELL: `cash += (qty * price - commission)`;
    `commission = max(commission_per_trade, qty * commission_per_share)`
    wird in `Fill.fee` gespeichert
  - `Trade.pnl` beruecksichtigt Entry- und Exit-Commission
    (bereits in `cash`-Buchung enthalten, automatisch korrekt)
  - Strukturiertes Logging: `backtest.stop_loss` (WARNING) bei
    Trigger mit Ticker, Entry-Price, Trigger-Price
- `src/quant_trader/backtest/__init__.py`: keine Aenderung noetig
  (alle Typen bereits exportiert)
- Tests: `tests/backtest/test_risk.py` (NEU, mind. 15 Tests):
  - Commission-Berechnung:
    - `max(per_trade, qty * per_share)` Korrektheit
    - Bei qty=0 Shares: nur per_trade greift
    - BUY: cash-Reduktion um qty*price + commission
    - SELL: cash-Erhohung um qty*price - commission
    - Trade.pnl inkl. Entry- + Exit-Commission
    - `Fill.fee` reflektiert Commission
  - Slippage:
    - BUY: fill_price = open * (1 + pct/100)
    - SELL: fill_price = open * (1 - pct/100)
    - Bei 0%: Fill-Preis = Open (Backward-Compat)
    - Fill-Simulator mit und ohne Slippage
  - Stop-Loss:
    - Bei Bar-Open < entry * (1 - stop_loss_pct/100): Position
      geschlossen vor Strategy-Signal
    - Stop-Loss-Trigger nur bei Long-Positionen (qty > 0)
    - Kein Trigger bei stop_loss_pct=None
    - Kein Trigger wenn Bar-Open noch ueber Schwelle
    - Strukturiertes Logging: `backtest.stop_loss` Event
  - Integration:
    - Komplett-Test: 100 USD Entry, 5% Stop, Open faellt auf 94 USD
      -> Position geschlossen, Trade erfasst, PnL negativ
    - Backward-Compat: BacktestConfig mit allen Defaults = 0 läuft
      wie bisher (gleicher PnL wie ohne Risk-Settings)
- `docs/requirements/nfrs.md`: keine Aenderung (NFRs bereits vorhanden)
- `docs/STATE.md`: Slice 4.1 auf DONE, Tag `p4-risk/4.1`
- `docs/adr/0010-risk-engine-architecture.md`: Status von `proposed`
  auf `accepted`

## Out of Scope (verbindlich)

- Tiered Commission (Volume-basiert, IBKR-Pro-Tier)
- Trailing-Stop-Loss (US-P4.3 explizit out)
- Take-Profit
- Time-basierter Exit
- Portfolio-Level Stop (max Drawdown)
- Intraday-Stop (z.B. Hit-Intraday-Low)
- Short-Selling / Margin (immer Long-only)
- Andere Waehrungen (alles USD)
- Risk-Adjustment (Volatility-Sizing, Risk-Parity) - Phase 6+

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies.
- Kein `print`, kein globaler State.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, Logs englisch.
- **Backward-Compat**: alle 355 bestehenden Tests MUESSEN unveraendert
  gruen bleiben. Defaults fuer neue Felder = 0.0 / None.
- `BacktestConfig` bleibt frozen dataclass.
- `Fill.fee` (existierendes Feld) wird wiederverwendet fuer Commission.
- `Trade`-Dataclass bleibt unveraendert (kein neues `reason`-Feld);
  Stop-Loss-Marker kommt nur ueber structlog-Event.
- `BacktestConfig` __init__-Defaults via Field-Default (nicht ueber
  `__post_init__`).

## Mapped NFRs

- NFR-Perf-1 (Backtest <30s fuer 5y Daily): minimaler Overhead
  (Stop-Loss-Check ist O(n_positions) pro Bar, Commission ist O(1) pro Fill)
- NFR-Data-2 (Adj. Close): nicht direkt betroffen
- NFR-Ux-1 (klare Logs): `backtest.stop_loss` mit Ticker + Preisen

## UML-Referenz

Visualisiert in: `docs/uml/p4-risk/risk-engine.md` (Status: wird auf
APPROVED gesetzt mit diesem Slice).

## Done when

- [ ] `src/quant_trader/backtest/types.py` mit erweiterten `BacktestConfig`
- [ ] `src/quant_trader/backtest/fill.py` mit Slippage-Logik in `FillSimulator`
- [ ] `src/quant_trader/backtest/engine.py` mit Commission-Buchung in
      `_apply_fill` und Stop-Loss-Check in `_run_single`/`_run_multi`
- [ ] Tests in `tests/backtest/test_risk.py` mit mind. 15 Tests
- [ ] `make test` gruen (alle 355 alten + neuen Tests, **alle ohne
      Aenderung** weiterhin gruen)
- [ ] `make lint` gruen
- [ ] `mypy --strict` gruen (0 errors, inkl. core/logging.py jetzt clean)
- [ ] ADR-0010 auf "accepted"
- [ ] Conventional Commit `feat(p4-risk): slice 4.1 risk engine`
- [ ] `docs/STATE.md` aktualisiert: Slice 4.1 auf DONE, Tag `p4-risk/4.1`

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p4-risk/risk.md
cat docs/adr/0010-risk-engine-architecture.md
cat docs/uml/p4-risk/risk-engine.md
cat docs/prd/p4-risk/risk-engine.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. Tiered-Commission,
  Trailing-Stop, etc. sind out.
- **KRITISCH**: alle bestehenden Tests muessen unveraendert gruen
  bleiben. Defaults = 0.0 / None erzwingen das.
- Wenn etwas Off-Scope auftaucht: STOP, dokumentiere, frage Nutzer.

Nach dem Coden:
- Conventional Commit mit `feat(p4-risk): slice 4.1 risk engine`.
- Commit-Body: warum Defaults = 0.0 (Backward-Compat), warum
  `Fill.fee` wiederverwendet (kein neuer Typ), warum kein
  `Trade.reason`-Feld (Marker ueber structlog).
