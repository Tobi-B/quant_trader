# Phase 5 - Live-Trading: User Stories

Phase:    P5 Live-Trading (IBKR)
Status:   US-P5.1 APPROVED (Slice 5.1, 2026-07-14, on "ja starten" Instruction)
          US-P5.2 DRAFT (Slice 5.2, wartet auf User-Approval)
Persona:  Tobias (privater Einsteiger-Trader)
Quelle:   Interview am 2026-07-14

Konvention: jede Story folgt INVEST + MoSCoW + T-Shirt-Size + Gherkin.
Nutzer-zentriert: das "Was & Warum", nicht das "Wie".

Slicing (5 Slices, genehmigt 2026-07-14):
- **Slice 5.1** Broker Interface + Mock + Order (Foundation)
- **Slice 5.2** Live Loop (Connect, Subscribe, Run)
- **Slice 5.3** Auto-Reconnect (NFR-Rel-2)
- **Slice 5.4** Tageszusammenfassung (NFR-Obs-2)
- **Slice 5.5** CLI + Credentials (NFR-Sec-2)

Globale Defaults (aus Interview, 2026-07-14):
- Broker: IBKR Paper Account (TWS verbindet sich auf Port 7497)
- ib_insync als optional `live` extra (Pyproject.toml)
- MockBroker fuer Tests (kein echter TWS noetig in CI)
- Order-Type: Market-Orders (Limit-Orders out-of-scope fuer P5)
- Live-Modus wird via Settings aktiviert (`live_enabled: bool = False`)

---

## Slice 5.1 - Broker Interface + Mock + Order

Schafft die Foundation fuer Live-Trading: ein einheitliches
`BrokerClient`-Interface, das sowohl vom `IBKRBroker` (real, via
`ib_insync`) als auch vom `MockBroker` (testbar) implementiert wird.
Order-Datentypen (`Order`, `OrderStatus`, `OrderType`) sind die
Sprache zwischen Strategie und Broker.

### US-P5.1 - Strategie sendet Market-Order ueber Broker-Abstraktion

- **Als** Trader
- **moechte ich**, dass meine registrierte Strategie ein BUY- oder
  SELL-Signal an einen Broker sendet (entweder Mock fuer Tests oder
  IBKR fuer Live), ohne dass die Strategie weiss, welcher Broker
  dahinter steckt,
- **damit** ich denselben Strategie-Code in Backtests, Tests und
  Live-Trading verwenden kann.

- **Priority:** Must
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** eine registrierte Strategie und ein `BrokerClient` (Mock oder IBKR)
  - **When** die Strategie ein BUY-Signal generiert
  - **Then** wird via `broker.place_order(ticker, action, qty)` ein Market-Order angelegt
  - **And** der Order hat eine `client_order_id` (UUID, generiert vom Broker)
  - **And** der Order-Status wird periodisch abgefragt (`PENDING -> SUBMITTED -> FILLED`)
  - **And** bei FILLED wird ein `Trade`-Record (Backtest-`Trade`-Typ) erzeugt mit
    Entry-Preis, Qty, Timestamp
  - **And** die Strategie kann nach dem Fill auf den offenen Positionen via
    `broker.get_positions()` arbeiten
  - **And** der `MockBroker` fuehrt Orders sofort (synchron) aus, der `IBKRBroker`
    nutzt `ib_insync`-Async-API
  - **And** bei Settings `live_enabled=False`: nur `MockBroker` wird genutzt
    (kein TWS-Connect, keine ib_insync-Import)

- **Out of Scope:** Limit-Orders, Stop-Orders, Trailing-Stops, Multi-Leg-Orders,
  Options/Futures (nur Stocks/ETFs), Short-Selling, Margin (Phase 6+),
  Auto-Reconnect (Slice 5.3), Tageszusammenfassung (Slice 5.4),
  Broker-Credentials-Persistierung (Slice 5.5).

### US-P5.2 - Live-Loop: Strategie empfängt Realtime-Bars und sendet Orders

- **Als** Trader
- **moechte ich**, dass eine Strategie auf echte Realtime-Bars vom
  Broker hoert und Signale direkt als Market-Order an den Broker
  sendet, waehrend alle Trades persistent in einem SQLite-Journal
  gespeichert werden,
- **damit** ich Live-Trading ohne manuellen Eingriff betreiben und
  alle Trades nachvollziehbar auditieren kann.

- **Priority:** Must
- **Estimate:** L
- **Acceptance Criteria (Gherkin):**
  - **Given** eine registrierte Strategie, ein `BrokerClient` (IBKR via
    `ib_insync` im Live-Modus oder MockBroker im Test-Modus) und ein
    `TradeJournal` (SQLite, Pfad aus Settings.db_path)
  - **When** ich `python -m quant_trader.live run --strategy sma_cross
    --ticker SPY --broker ibkr --duration 1h` aufrufe
  - **Then** verbindet sich der Live-Loop mit dem Broker (Mock: sofort
    ready; IBKR: `ib.connect()` zu TWS)
  - **And** abonniert Realtime-Bars fuer die angegebenen Ticker
    (IBKR: `ib.reqRealTimeBars()`; Mock: synthetische Bars aus
    deterministischem Generator)
  - **And** bei jedem neuen Bar: `strategy.on_bar(bar, portfolio)` ->
    Signale -> `broker.place_order()` -> bei FILLED: `TradeJournal.append()`
  - **And** jeder Trade (Entry + Exit) landet persistent in
    `quant_trader.sqlite` mit Feldern: `id, run_id, strategy_name, ticker,
    action, qty, entry_price, exit_price, pnl, pnl_pct, opened_at, closed_at`
  - **And** `run_id` ist UUID, pro Loop-Run eineindeutig
  - **And** nach `duration` (oder Ctrl-C) wird der Loop sauber beendet:
    Broker disconnect, Journal geschlossen, Summary-Log
  - **And** bei Fehler (Broker disconnect, TWS nicht erreichbar): klarer
    Log + Exit 1 (Auto-Reconnect kommt in Slice 5.3)

- **Out of Scope:** Auto-Reconnect (Slice 5.3), Tageszusammenfassung
  (Slice 5.4), Credentials-Persistierung (Slice 5.5),
  Multi-Strategy parallel, Multi-Ticker Universe (kommt spaeter),
  Real-time-Equity-Update, WebSocket-Dashboard, Backtest-Engine-Bridge
  (BacktestEngine bleibt eigenstaendig fuer Phase 3).

---

## Mapped NFRs (siehe docs/requirements/nfrs.md)

| Story   | NFR-IDs                                            |
|---------|----------------------------------------------------|
| US-P5.1 | NFR-Sec-2 (Credentials via TWS only), NFR-Obs-1    |
| US-P5.2 | NFR-Obs-1, NFR-Rel-1 (idempotente Trades via Journal UNIQUE-Constraint) |

---

## Definition of Done (Story 5.1)

- [ ] `BrokerClient` Protocol (place_order, get_positions, is_connected)
- [ ] `Order` Dataclass (id, client_order_id, ticker, action, qty, type, status, filled_qty, avg_fill_price, created_at, updated_at)
- [ ] `OrderStatus` StrEnum (PENDING, SUBMITTED, FILLED, CANCELLED, REJECTED)
- [ ] `OrderType` StrEnum (MARKET, LIMIT) - nur MARKET genutzt in P5
- [ ] `Action` StrEnum (BUY, SELL) - bereits in `quant_trader.strategies.types`
- [ ] `MockBroker` mit deterministischem Fill (synchron, sofort FILLED)
- [ ] `IBKRBroker` (Stub + Placeholders; echt in Slice 5.2)
- [ ] `BrokerFactory` (Settings-driven: live_enabled -> Mock vs IBKR)
- [ ] Settings: `live_enabled: bool = False`
- [ ] Tests fuer `MockBroker` (deterministische State-Machine, mind. 8 Tests)
- [ ] Tests fuer `BrokerFactory` (mind. 3 Tests)
- [ ] ib_insync-Import nur in `IBKRBroker`-Datei mit try/except
- [ ] `make test`, `make lint`, `mypy --strict` gruen
- [ ] Conventional Commits
- [ ] `docs/STATE.md` aktualisiert, Tag `p5-live/5.1` gesetzt
- [ ] UML-Diagramm (Structure + Flow + Sequence) APPROVED
