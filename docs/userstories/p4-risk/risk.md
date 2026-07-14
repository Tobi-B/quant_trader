# Phase 4 - Risk Management: User Stories

Phase:    P4 Risk Management
Status:   US-P4.1 bis US-P4.3 DRAFT (Slice 4.1, wartet auf User-Approval)
Persona:  Tobias (privater Einsteiger-Trader)
Quelle:   Interview am 2026-07-14

Konvention: jede Story folgt INVEST + MoSCoW + T-Shirt-Size + Gherkin.
Nutzer-zentriert: das "Was & Warum", nicht das "Wie".

Slicing (1 grosser Slice, genehmigt 2026-07-14):
- **Slice 4.1** Risk-Engine (Commission + Slippage + Stop-Loss)

Globale Defaults (aus Interview, 2026-07-14):
- Commission: 1.00 USD pro Trade + 0.01 USD pro Share (IBKR-Standard)
- Slippage: 0% (default aus, konfigurierbar)
- Stop-Loss: deaktiviert (default None, konfigurierbar in Prozent vom Entry)

---

## Slice 4.1 - Risk-Engine

Erweitert den BacktestEngine (Slice 3.1) um realistische Kosten
(Commission, Slippage) und ein Risiko-Limit (Stop-Loss). Die Defaults
sind "kostenfrei" (Commission/Slippage = 0, kein Stop-Loss), damit
bestehende Tests ohne Aenderung gruen bleiben.

### US-P4.1 - Commission pro Trade (IBKR-Stil)

- **Als** Trader
- **moechte ich**, dass pro Fill eine Commission berechnet und vom Cash
  abgezogen wird (1 USD fix pro Trade plus 0.01 USD pro Share),
- **damit** mein Backtest realistische Netto-Returns zeigt, die die
  Broker-Gebuehren beruecksichtigen.

- **Priority:** Should
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** ein Backtest mit `commission_per_trade=1.0` und `commission_per_share=0.01`
  - **When** ein BUY fuer 100 Shares zu Preis 50 USD gefillt wird
  - **Then** betraegt die Commission `max(1.0, 100 * 0.01) = max(1.0, 1.0) = 1.0` USD
  - **And** der Cash wird um `qty * price + commission` reduziert (Cost-Basis + Commission)
  - **And** beim SELL wird die Commission ebenfalls vom Erloes abgezogen
  - **And** die Commission erscheint als `fee`-Feld im `Fill` (default 0.0)
  - **And** Commission-Aufschlag wird im `Trade.pnl` als Kostenkomponente
    sichtbar (Entry-Commission + Exit-Commission vom PnL abgezogen)
  - **And** bei `commission_per_trade=0.0` und `commission_per_share=0.0`: kein
    Cash-Abzug, Backtest verhaelt sich wie bisher (Backward-Compat)

- **Out of Scope:** Tiered-Pricing (Volumen-basiert), Min/Max-Commission
  pro Tag, andere Waerungen (alles USD).

### US-P4.2 - Slippage pro Trade

- **Als** Trader
- **moechte ich**, dass der Fill-Preis um einen Slippage-Prozentsatz
  zu meinen Ungunsten verschoben wird (z.B. 0.1% auf den Open-Preis),
- **damit** der Backtest die realen Marktausfuehrungskosten naeherungsweise abbildet.

- **Priority:** Could
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** ein Backtest mit `slippage_pct=0.1` (0.1%)
  - **When** ein BUY-Signal bei Open-Preis 100 USD gefillt wird
  - **Then** betraegt der effektive Fill-Preis `100 + (100 * 0.1 / 100) = 100.10` USD
  - **And** bei SELL: Fill-Preis = Open - Slippage (`99.90` USD bei 0.1% und Open 100)
  - **And** Slippage wird in `Fill.price` reflektiert (nicht als separater Fee)
  - **And** bei `slippage_pct=0.0`: Fill-Preis = Open (kein Effekt, Backward-Compat)

- **Out of Scope:** Volume-abhaengiger Slippage, variable Slippage pro
  Tageszeit, Market-Impact-Modelle.

### US-P4.3 - Stop-Loss pro Position

- **Als** Trader
- **moechte ich**, dass eine offene Position automatisch geschlossen wird,
  sobald der Preis um mehr als X Prozent gegen mich laeuft (z.B. -5% vom
  Entry-Preis),
- **damit** mein Backtest das Downside-Risiko pro Trade begrenzt.

- **Priority:** Should
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** ein Backtest mit `stop_loss_pct=5.0` (5%) und eine offene
    Long-Position mit Entry-Preis 100 USD
  - **When** eine Bar mit Open-Preis 94 USD (mehr als 5% unter Entry) verarbeitet wird
  - **Then** wird die Position vor der Strategie-Abfrage zum Open der Bar
    geschlossen (SELL-Fill zum Open-Preis abzueglich Slippage, falls aktiv)
  - **And** der Stop-Loss-Trade wird im `result.trades` mit `reason="stop_loss"`
    oder aehnlichem Marker erfasst
  - **And** nach dem Stop-Loss-Trigger hat der Trader fuer den Rest des
    Tages keine offene Position mehr
  - **And** bei `stop_loss_pct=None` (default): kein Stop-Loss-Check
    (Backward-Compat)
  - **And** wenn mehrere Ticker gleichzeitig Stop-Loss triggern: jeder
    wird einzeln in chronologischer Reihenfolge verarbeitet

- **Out of Scope:** Trailing-Stop-Loss, Take-Profit, Time-basierter
  Exit, Stop-Loss auf Portfolio-Ebene (max Drawdown), Intraday-Stop
  (z.B. Hit-Intraday-Low vs Tagesschluss).

---

## Mapped NFRs (siehe docs/requirements/nfrs.md)

| Story   | NFR-IDs                                              |
|---------|------------------------------------------------------|
| US-P4.1 | NFR-Perf-1 (Backtest <30s), NFR-Data-2 (Adj. Close) |
| US-P4.2 | NFR-Perf-1                                            |
| US-P4.3 | NFR-Perf-1, NFR-Ux-1 (klare Logs: stop_loss)         |

---

## Definition of Done (alle Stories)

- [ ] Commission berechnet pro Fill (BacktestConfig-Parameter, IBKR-Default)
- [ ] Slippage angewendet auf Fill-Preis (BacktestConfig-Parameter)
- [ ] Stop-Loss-Trigger vor Strategie-Signal, chronologisch korrekt
- [ ] Backward-Compat: alle 355 bestehenden Tests bleiben gruen ohne Aenderung
- [ ] `make test`, `make lint`, `mypy --strict` gruen
- [ ] Conventional Commits (ein Slice = ein Commit-Body)
- [ ] `docs/STATE.md` aktualisiert, Tag `p4-risk/4.1` gesetzt
- [ ] UML-Diagramm (Structure + Flow + Sequence) APPROVED
