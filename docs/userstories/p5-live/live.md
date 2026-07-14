# Phase 5 - Live-Trading: User Stories

Phase:    P5 Live-Trading (IBKR)
Status:   US-P5.1, US-P5.2 APPROVED (Slices 5.1, 5.2, 2026-07-14)
          US-P5.3-US-P5.5 DRAFT (Slice 5.3, wartet auf User-Approval)
Persona:  Tobias (privater Einsteiger-Trader)
Quelle:   Interview am 2026-07-14

Konvention: jede Story folgt INVEST + MoSCoW + T-Shirt-Size + Gherkin.
Nutzer-zentriert: das "Was & Warum", nicht das "Wie".

Slicing (3 Slices, genehmigt 2026-07-14):
- **Slice 5.1** Broker Interface + Mock + Order (Foundation)
- **Slice 5.2** Live Loop + Trade-Journal + Live-CLI
- **Slice 5.3** Auto-Reconnect + Tageszusammenfassung + Credentials (1 grosser Slice)

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

### US-P5.3 - Live-Loop uebersteht TWS-Disconnect mit Auto-Reconnect

- **Als** Trader
- **moechte ich**, dass der Live-Loop einen TWS-Disconnect erkennt,
  automatisch versucht, sich neu zu verbinden (mit Backoff), und
  bestehende Realtime-Bar-Subscriptions wiederherstellt,
- **damit** mein Live-Trading auch bei kurzen Netzwerk-Issues robust
  weiterlaeuft, ohne dass ich manuell eingreifen muss.

- **Priority:** Must
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** ein laufender Live-Loop mit IBKRBroker
  - **When** TWS disconnectet (z.B. `ib.connectionClosed()` Callback)
  - **Then** loggt der Loop `live_loop.broker_disconnected` WARNING
  - **And** nach `reconnect_initial_delay` (Default 1s) wird
    `broker.connect()` aufgerufen, bei Fehler mit Backoff verdoppelt
    (1s, 2s, 4s, max `reconnect_max_delay`, Default 30s)
  - **And** nach erfolgreichem Reconnect werden alle aktiven
    `RealtimeBarSource.subscribe(ticker)`-Subscriptions wiederhergestellt
  - **And** offene Positionen werden via `broker.get_positions()`
    re-synchronisiert (Journal bleibt unveraendert)
  - **And** nach `reconnect_max_attempts` (Default 10) erfolglosen
    Versuchen: `live_loop.reconnect_failed` ERROR, Loop beendet sich
    sauber mit Exit 1
  - **And** bei `MockBroker`: kein Reconnect noetig (immer connected),
    der Mechanismus wird nur fuer IBKR aktiv

- **Out of Scope:** Permanent-Failure-Handling (z.B. TWS komplett
  tot), Resume von offenen Signalen (Strategie setzt nach Reconnect
  fort mit neuem State), Multi-Region-Redundanz.

### US-P5.4 - Tageszusammenfassung beim Beenden des Live-Loops

- **Als** Trader
- **moechte ich**, dass beim Beenden des Live-Loops (Ctrl-C oder
  duration abgelaufen) eine Tageszusammenfassung geloggt und auf
  stdout gedruckt wird mit Anzahl Trades, P&L, offene Positionen,
- **damit** ich ohne manuelles Query sofort sehe, wie der heutige
  Live-Tag gelaufen ist.

- **Priority:** Should
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** ein Live-Loop-Run mit N Trades
  - **When** der Loop sauber beendet (Ctrl-C, duration, oder error)
  - **Then** wird `live_loop.daily_summary` Log mit folgenden Feldern
    emittiert: `run_id`, `strategy_name`, `total_trades`,
    `open_positions_count`, `total_pnl`, `duration_seconds`
  - **And** auf stdout wird eine formatierte Tabelle (deutsch,
    fixed-width) gedruckt mit den gleichen Feldern + Entry/Exit-
    Summary pro Trade (max 10 Top-Trades, dann Footer "... N weitere")
  - **And** die Summary wird im Journal als Tagesabschluss
    persistiert (neue Tabelle `daily_summaries` mit run_id,
    strategy_name, total_trades, open_positions_count, total_pnl,
    duration_seconds, closed_at)

- **Out of Scope:** E-Mail/Slack-Benachrichtigung, Web-Dashboard-
  Anzeige, Multi-Day-Aggregation, Steuer-Reports.

### US-P5.5 - Broker-Credentials via TWS ohne Persistenz

- **Als** Trader
- **moechte ich**, dass der IBKRBroker die TWS-Verbindung OHNE
  Credentials-Speicherung aufbaut (TWS-Prompt bestaetigt manuell),
  und dass die Settings keine sensiblen Felder enthalten,
- **damit** meine Broker-Credentials niemals ins Repo oder in eine
  Datei gelangen (NFR-Sec-2).

- **Priority:** Must
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** die Live-CLI wird mit `--broker ibkr` gestartet
  - **When** der IBKRBroker versucht zu connecten
  - **Then** wird `ib.connect(host, port, clientId)` ohne
    Credentials-Parameter aufgerufen (TWS-Prompt erscheint manuell)
  - **And** in `Settings` gibt es KEINE Felder fuer `username`,
    `password`, `api_key` o.ae.
  - **And** in `.env.example` (oder `.env.template`) wird dokumentiert,
    dass KEINE Broker-Credentials noetig sind (nur TWS-Login)
  - **And** in `docs/SECURITY.md` (oder in STATE.md) wird festgehalten:
    "Credentials ausschliesslich via TWS-Login, niemals persistiert"

- **Out of Scope:** OAuth-Token-basierte Auth (IBKR verwendet keine
  API-Tokens, nur TWS-Login), Credential-Rotation, MFA-Handling
  (TWS-seitig).

---

## Mapped NFRs (siehe docs/requirements/nfrs.md)

| Story   | NFR-IDs                                            |
|---------|----------------------------------------------------|
| US-P5.1 | NFR-Sec-2 (Credentials via TWS only), NFR-Obs-1    |
| US-P5.2 | NFR-Obs-1, NFR-Rel-1 (idempotente Trades via Journal UNIQUE-Constraint) |
| US-P5.3 | NFR-Rel-2 (Auto-Reconnect), NFR-Obs-1 (Logs)        |
| US-P5.4 | NFR-Obs-2 (Tageszusammenfassung), NFR-Obs-1 (Logs)  |
| US-P5.5 | NFR-Sec-2 (Credentials via TWS only)               |

---

## Definition of Done (alle Stories)

- [ ] `BrokerClient` Protocol + `MockBroker` + `IBKRBroker` (Slice 5.1)
- [ ] `TradeJournal` (SQLite), `LiveLoop` async, `MockBarSource`,
      `IBKRBarSource`, `python -m quant_trader.live` CLI (Slice 5.2)
- [ ] Auto-Reconnect mit Exponential-Backoff (Slice 5.3, US-P5.3)
- [ ] Tageszusammenfassung beim Beenden: Log + stdout + `daily_summaries`
      Tabelle im Journal (Slice 5.3, US-P5.4)
- [ ] Credentials via TWS only, KEINE in Settings, Doku aktualisiert
      (Slice 5.3, US-P5.5)
- [ ] `make test`, `make lint`, `mypy --strict` gruen
- [ ] Backward-Compat: alle 417 bestehenden Tests bleiben unveraendert gruen
- [ ] Conventional Commits
- [ ] `docs/STATE.md` aktualisiert, Tag `p5-live/5.3` gesetzt
- [ ] UML-Diagramm (Structure + Flow + Sequence) APPROVED
