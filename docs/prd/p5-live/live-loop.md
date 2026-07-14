# PRD: Slice 5.2 - Live-Loop (Realtime-Bars + Order-Placement + Trade-Journal)

Phase:    P5 Live-Trading (IBKR)
Slice:    5.2 Live-Loop + Trade-Journal + Live-CLI
Status:   DRAFT  (User "weiter mit naechstem slice" gilt als implizite Approval; UML auf APPROVED setzen)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Den eigentlichen Live-Trading-Loop implementieren: Realtime-Bars
empfangen, an registrierte Strategie weiterleiten, Signale via
`BrokerClient` ausfuehren und alle Trades persistent in einem
SQLite-Journal speichern. Plus eine `python -m quant_trader.live` CLI
zum Starten/Listen von Runs.

Auto-Reconnect (Slice 5.3), Tageszusammenfassung (Slice 5.4) und
Credentials-Persistierung (Slice 5.5) folgen.

## Scope (IN)

- `src/quant_trader/live/journal.py` (NEU):
  - `TradeRow` (frozen dataclass): alle SQLite-Spalten
  - `TradeJournal` Klasse:
    - `__init__(db_path: Path)`: oeffnet SQLite, erstellt Tabelle +
      Index, konfiguriert WAL-Mode
    - `append_open(run_id, strategy_name, ticker, action, qty, price, client_order_id, opened_at) -> int`
      - INSERT in `trades`, `client_order_id` UNIQUE-Constraint
      - Konflikt -> `sqlite3.IntegrityError` (Caller faengt ab, loggt)
    - `close_trade(client_order_id, exit_price, closed_at) -> None`:
      - UPDATE entry_price=NULL, exit_price=..., pnl=qty*(exit-entry), pnl_pct=pnl/(qty*entry), closed_at=...
    - `list_trades(run_id=None) -> list[TradeRow]`: SELECT
    - `close() -> None`: DB-Connection schliessen
- `src/quant_trader/live/bars.py` (NEU):
  - `RealtimeBarSource` Protocol: `subscribe(ticker)`, `next_bar() async`, `stop()`
  - `MockBarSource` Klasse: deterministisch via `_inject(bar)` Methode
    (Tests rufen `inject` direkt auf, kein asyncio-Queue noetig in
    5.2-Tests); Default: 1 Bar pro Sekunde wenn nicht gemockt
  - `IBKRBarSource` Klasse: nutzt `ib_insync.IB.reqRealTimeBars()`,
    `pendingRealTimeBars()` Polling in 1s-Loop (slice 5.2 nutzt
    `asyncio.sleep(1)` + `ib.sleep(0)` Pattern)
- `src/quant_trader/live/loop.py` (NEU):
  - `LiveLoop` Klasse mit `__init__(strategy, broker, source, journal, run_id, duration: timedelta | None)`
  - `async def run(self) -> LiveLoopSummary`:
    - broker.connect() falls noetig
    - pro ticker: `source.subscribe(ticker)`
    - `portfolio_state = PortfolioState(cash=0, positions=broker.get_positions())`
    - `open_trades: dict[client_order_id, TradeRow]` (offene Positionen)
    - Loop: `bar = await source.next_bar()` (raised `StopAsyncIteration` bei duration abgelaufen)
    - `signals = strategy.on_bar(bar, portfolio_state)`
    - pro signal: `order = broker.place_order(...)`
    - bei FILLED:
      - BUY: `journal.append_open(...)` mit `opened_at=order.updated_at`
      - SELL: schliesse offene Position via `journal.close_trade(...)`
    - nach Loop: `source.stop()`, `broker.disconnect()`, `journal.close()`
    - return `LiveLoopSummary(run_id, total_signals, total_trades, total_pnl)`
  - `LiveLoopSummary` (frozen dataclass): run_id, total_signals, total_trades, total_pnl
- `src/quant_trader/live/cli.py` (NEU):
  - `build_parser()` mit Subcommands:
    - `run --strategy X --ticker Y [--broker mock|ibkr] [--duration 1h]`
    - `list [--run-id UUID]`
  - `main(argv) -> int`: parsed args, baut `StrategyLoader`,
    `BrokerFactory`, `TradeJournal`, `MockBarSource` oder
    `IBKRBarSource`, `LiveLoop`, ruft `asyncio.run(loop.run())`,
    Exit 0/1
  - Deutsche Fehlermeldungen (NFR-Ux-1)
- `src/quant_trader/live/__main__.py` (NEU): ruft `cli.main()`
- `src/quant_trader/live/__init__.py` (aendern): exportiert `LiveLoop`,
  `LiveLoopSummary`, `TradeJournal`, `TradeRow`, `MockBarSource`,
  `IBKRBarSource`, `RealtimeBarSource`
- `src/quant_trader/live/ibkr.py` (aendern): `IBKRBroker.place_order`,
  `get_positions`, `is_connected` jetzt vollstaendig (statt
  `NotImplementedError`); nutzt `ib_insync.MarketOrder`,
  `ib_insync.OrderState.Filled` etc.
- Tests: `tests/live/test_journal.py`, `test_loop.py`, `test_cli.py`,
  `test_bars.py` (NEU, gesamt mind. 20 Tests):
  - **Journal** (mind. 8 Tests):
    - `test_journal_creates_table_on_init`
    - `test_journal_append_open_inserts_row`
    - `test_journal_append_open_duplicate_client_order_id_raises_integrity_error`
    - `test_journal_close_trade_updates_pnl`
    - `test_journal_list_trades_by_run_id`
    - `test_journal_list_trades_all`
    - `test_journal_close_releases_connection`
    - `test_journal_wal_mode_enabled`
  - **Bars** (mind. 4 Tests):
    - `test_mock_bar_source_subscribe_no_error`
    - `test_mock_bar_source_inject_then_next`
    - `test_ibkr_bar_source_constructs_without_connect` (mit Mock)
    - `test_bar_source_protocol_satisfied` (runtime-checkable Test)
  - **Loop** (mind. 5 Tests):
    - `test_loop_runs_until_duration`
    - `test_loop_invokes_strategy_on_bar`
    - `test_loop_places_buy_order_on_signal`
    - `test_loop_closes_trade_on_sell_signal`
    - `test_loop_summary_includes_run_id_and_pnl`
  - **CLI** (mind. 3 Tests):
    - `test_parser_run_minimal`
    - `test_parser_list`
    - `test_cli_returns_0_on_mock_run` (mit gemocktem Loop)
    - `test_cli_returns_1_on_broker_error`
- Doku-Updates:
  - `docs/STATE.md`: Slice 5.2 auf DONE, Tag `p5-live/5.2`
  - `docs/adr/0012-live-loop-architecture.md`: Status `proposed` -> `accepted`

## Out of Scope (verbindlich)

- Auto-Reconnect bei TWS-Disconnect (Slice 5.3)
- Tageszusammenfassung beim Beenden (Slice 5.4)
- Credentials-Persistierung / TWS-Auth-Flow (Slice 5.5)
- Multi-Strategy parallel (single Strategy pro Run)
- Multi-Ticker Universe (nur single ticker; --universe kommt spaeter)
- Real-time-Equity-Update im UI
- WebSocket-Dashboard (Streamlit-Erweiterung)
- BacktestEngine -> LiveLoop-Bridge (BacktestEngine bleibt Phase 3)
- Order-Modification (nur Market-Orders, nicht Limit)
- Partial-Fill-Handling (FILLED = full fill)
- Trade-Migration bei Schema-Aenderung
- Live-Run-Scheduling (cron, systemd)

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies (sqlite3 + asyncio + ib_insync bereits da)
- Kein `print`, kein globaler State.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, CLI-Strings deutsch (NFR-Ux-1).
- `TradeJournal` oeffnet DB in `__init__`, schliesst in `close()`
  (deterministisches Lifecycle).
- `LiveLoop.run` ist `async`, in CLI via `asyncio.run()`.
- `MockBarSource._inject(bar)` ermoeglicht deterministische Tests
  (kein sleep, kein random).
- `IBKRBarSource.place_order` nutzt `ib_insync` mit `try/except` an
  Modul-Top, sodass Tests ohne ib_insync lauffaehig bleiben.
- `client_order_id` UNIQUE-Constraint garantiert Idempotenz.
- Backward-Compat: alle 394 bestehenden Tests unveraendert gruen.

## Mapped NFRs

- NFR-Rel-1 (Daten-Fetch idempotent) - ueber `client_order_id` UNIQUE
- NFR-Rel-3 (Order-Manager idempotent) - via UNIQUE-Constraint
- NFR-Obs-1 (structlog) - `live_loop.start`, `live_loop.bar_received`,
  `live_loop.signal`, `live_loop.order_placed`, `live_loop.complete`
- NFR-Ux-1 (deutsche CLI-Texte) - CLI-Fehlermeldungen deutsch

## UML-Referenz

Visualisiert in: `docs/uml/p5-live/live-loop.md` (Status: wird auf
APPROVED gesetzt mit diesem Slice).

## Done when

- [ ] `src/quant_trader/live/journal.py` mit `TradeJournal` und `TradeRow`
- [ ] `src/quant_trader/live/bars.py` mit `RealtimeBarSource`, `MockBarSource`, `IBKRBarSource`
- [ ] `src/quant_trader/live/loop.py` mit `LiveLoop` und `LiveLoopSummary`
- [ ] `src/quant_trader/live/cli.py` mit `build_parser` und `main`
- [ ] `src/quant_trader/live/__main__.py` als Entry-Point
- [ ] `src/quant_trader/live/ibkr.py` jetzt vollstaendig (kein Stub mehr)
- [ ] Tests in `tests/live/` mit gesamt mind. 20 Tests
- [ ] `make test` gruen (alle 394 alten + neuen Tests)
- [ ] `make lint` gruen
- [ ] `mypy --strict` gruen (0 errors)
- [ ] Conventional Commit `feat(p5-live): slice 5.2 live loop`
- [ ] `docs/STATE.md` aktualisiert: Slice 5.2 auf DONE, Tag `p5-live/5.2`
- [ ] ADR-0012 auf "accepted"

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p5-live/live.md
cat docs/adr/0012-live-loop-architecture.md
cat docs/uml/p5-live/live-loop.md
cat docs/prd/p5-live/live-loop.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. Auto-Reconnect in 5.3,
  Tageszusammenfassung in 5.4, Credentials in 5.5.
- **KRITISCH**: alle 394 bestehenden Tests muessen unveraendert gruen
  bleiben. Keine bestehenden Dateien aendern ausser den genannten.
- Wenn etwas Off-Scope auftaucht: STOP, dokumentiere, frage Nutzer.

Nach dem Coden:
- Conventional Commit mit `feat(p5-live): slice 5.2 live loop`.
- Commit-Body: warum sqlite3 + UNIQUE-Constraint (Idempotenz ohne
  Retry-Logik), warum `MockBarSource._inject()` (deterministische
  Tests), warum LiveLoop async (ib_insync erfordert asyncio).
