# ADR 0012: Live-Loop-Architektur (Realtime-Bars + Order-Placement + Trade-Journal)

Status:     proposed
Datum:      2026-07-14
Phase:      P5 Live-Trading
Supersedes: -
Superseded by: -

## Context

Slice 5.1 hat das Broker-Interface (`BrokerClient`, `MockBroker`,
`IBKRBroker` Stub) geliefert. Fuer echtes Live-Trading fehlt aber
die **Live-Loop**, die:
1. Realtime-Bars vom Broker empfaengt (IBKR: `reqRealTimeBars`)
2. An die registrierte Strategie weiterleitet
3. Resultierende Signale via `BrokerClient.place_order` ausfuehrt
4. Alle Trades persistent in SQLite speichert (Journal/Audit-Trail)

Im Repo vorhanden:
- `quant_trader/live/` mit Protocol + Mock + IBKR-Stub + Factory
- `core/config.py` hat `db_path: Path = Path("./quant_trader.sqlite")`
- `strategies/` hat `StrategyBase.on_bar(bar, portfolio) -> list[Signal]`
- 394 Tests gruen (alle vorherigen Slices + 5.1)

## Decision

### 1. Module-Struktur (Erweiterung von `live/`)

```
src/quant_trader/live/
  (existiert: types.py, protocol.py, mock.py, ibkr.py, factory.py)
  journal.py     # NEU: TradeJournal (SQLite)
  loop.py        # NEU: LiveLoop (async, Broker + Strategy + Journal)
  bars.py        # NEU: RealtimeBarSource (Protocol + IBKR + Mock-Generator)
  cli.py         # NEU: Live-CLI (python -m quant_trader.live run ...)
  __main__.py    # NEU: Entry-Point
```

### 2. `TradeJournal` (SQLite)

Schema:
```sql
CREATE TABLE IF NOT EXISTS trades (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id          TEXT NOT NULL,
  strategy_name   TEXT NOT NULL,
  ticker          TEXT NOT NULL,
  action          TEXT NOT NULL,  -- BUY | SELL
  qty             INTEGER NOT NULL,
  entry_price     REAL,
  exit_price      REAL,
  pnl             REAL,
  pnl_pct         REAL,
  opened_at       TEXT NOT NULL,  -- ISO-8601
  closed_at       TEXT,
  client_order_id TEXT UNIQUE,   -- NFR-Rel-3 Idempotenz
  created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_trades_run_id ON trades(run_id);
```

Methoden:
- `__init__(db_path: Path)`
- `append_open(run_id, strategy_name, ticker, action, qty, price, client_order_id, opened_at)`
  - `client_order_id` UNIQUE-Constraint garantiert Idempotenz (NFR-Rel-1/-3)
- `close_trade(client_order_id, exit_price, closed_at)` -> berechnet pnl, pnl_pct
- `list_trades(run_id: str | None = None) -> list[TradeRow]`
- `close()` schliesst DB-Connection

Verwendet `sqlite3` aus stdlib. KEIN neues Package.

### 3. `RealtimeBarSource` Protocol

```python
class RealtimeBarSource(Protocol):
    def subscribe(self, ticker: str) -> None: ...
    async def next_bar(self) -> Bar: ...
    def stop(self) -> None: ...
```

- `IBKRBarSource`: nutzt `ib.reqRealTimeBars(ticker, 5, "TRADES", False)`
  und liest Bars aus `ib.pendingRealTimeBars()`. Stop via
  `ib.cancelRealTimeBars()`. VOLLSTAENDIG in 5.2.
- `MockBarSource`: deterministischer Generator (z.B. via simple
  random-walk mit seed), publiziert Bars in einer asyncio-Queue.
  Tests koennen `time.sleep` durch direkten `source._inject(bar)` ersetzen.

### 4. `LiveLoop`

```python
class LiveLoop:
    def __init__(self, strategy, broker, source, journal, run_id, duration):
        self._strategy = strategy
        self._broker = broker
        self._source = source
        self._journal = journal
        self._run_id = run_id
        self._duration = duration

    async def run(self) -> None:
        # 1. broker.is_connected() pruefen, ggf. broker.connect()
        # 2. source.subscribe(ticker) fuer jeden gewuenschten Ticker
        # 3. Portfolio-State aufbauen aus broker.get_positions()
        # 4. Solange duration nicht abgelaufen:
        #    bar = await source.next_bar()
        #    signals = strategy.on_bar(bar, portfolio_state)
        #    for signal in signals:
        #        order = broker.place_order(signal.ticker, signal.action, qty)
        #        if order.status == FILLED:
        #            journal.append_open(...)
        #    if action == SELL: close_trade via client_order_id
        # 5. source.stop(), broker.disconnect(), journal.close()
        # 6. log live_loop.complete mit summary
```

`run_id` ist UUID, einmal pro Loop-Start.
`duration` ist `timedelta`; bei None laeuft der Loop bis Ctrl-C.

### 5. `Live-CLI` (`python -m quant_trader.live`)

Subcommands:
- `run --strategy X --ticker Y [--broker mock|ibkr] [--duration 1h]`
- `list [--run-id UUID]`: zeigt Trades aus Journal

Exit 0 bei normaler Beendigung, 1 bei Fehler.

### 6. ib_insync-Handling

- `IBKRBarSource` und `IBKRBroker.place_order` (in 5.1 als Stub) sind
  jetzt vollstaendig
- ImportError-Handling: in `live/ibkr.py` bleibt `SystemExit` bei
  fehlendem `ib_insync`; in `live/cli.py` und `live/loop.py` KEIN
  top-level ib_insync-Import
- Tests in `tests/live/` bleiben ohne ib_insync lauffaehig

### 7. Backward-Compat

- Alle 394 bestehenden Tests unveraendert gruen
- `MockBroker`, `IBKRBroker` aus 5.1 unveraendert
- `BrokerFactory` unveraendert

## Consequences

**Positiv**
- Vollstaendiges Live-Trading in einem Slice (5.2)
- Trade-Journal in SQLite ermoeglicht Audit-Trail (Compliance, Debug)
- `client_order_id` UNIQUE-Constraint garantiert Idempotenz
  (NFR-Rel-1, NFR-Rel-3)
- MockBarSource macht Tests deterministisch (kein sleep, kein random)
- Live-CLI mit `python -m quant_trader.live run ...` ergonomisch
- Backward-Compat: 394 alte Tests unveraendert gruen

**Negativ**
- IBKRBarSource + IBKRBroker.place_order sind komplex (asyncio
  mit ib_insync); Tests nur Mock-BarSource
- Trade-Schema in SQLite ist v1; Migration-Skripte fuer Schema-
  Aenderungen kommen spaeter (YAGNI)
- SQLite ist single-writer; Multi-Strategy parallel braucht
  separate DB-Connections (out of scope)
- duration als timedelta (max 24h sinnvoll), kein Wochenend-Handling

**Neutral**
- Live-Loop ist async (`asyncio.run()`) - vorhandene Strategien
  bleiben sync (on_bar ist sync)
- `IBKRBarSource.start()` oeffnet Subscription, `stop()` schliesst
- Bei Tests: `MockBarSource._inject(bar)` direkt aufrufen statt
  `await source.next_bar()`

## Alternatives Considered

- **Async-Strategien**: abgelehnt, on_bar bleibt sync
- **PostgreSQL statt SQLite**: abgelehnt, SQLite ist stdlib und
  reicht fuer persoenlichen Use-Case
- **WebSocket-basierte Bars (z.B. Polygon)**: out of scope, P5 = IBKR
- **Reconnect in 5.2 integriert**: abgelehnt, eigener Slice 5.3
- **Order-Retry-Logik**: out of scope; Idempotenz via UNIQUE-Constraint
  reicht fuer 5.2
- **Live-Dashboard (Streamlit-Erweiterung)**: out of scope, Phase 6+
- **Tageszusammenfassung beim Beenden**: Slice 5.4
- **Credentials via CLI-Flag**: out of scope, Slice 5.5 (Settings)

## References

- `src/quant_trader/live/` (erweitert in 5.2)
- `src/quant_trader/core/config.py` (Settings.db_path, live_enabled)
- `docs/userstories/p5-live/live.md` (US-P5.2)
- `docs/prd/p5-live/live-loop.md` (Slice-PRD)
- `docs/uml/p5-live/live-loop.md` (Mermaid Structure/Flow/Sequence)
- NFR-Rel-1 (Daten-Fetch idempotent)
- NFR-Rel-3 (Order-Manager idempotent)
- NFR-Obs-1 (structlog)
- Slice 5.1 ADR-0011 (Pattern: Protocol + Mock + IBKR)
