# UML: Slice 5.2 - Live-Loop (Realtime-Bars + Order-Placement + Trade-Journal)

Status:    APPROVED
Phase:     P5 Live-Trading
Slice:     5.2 Live-Loop + Trade-Journal + Live-CLI
Approved:  2026-07-14

Mapped Requirements:
- NFR-Rel-1: Daten-Fetch idempotent (client_order_id UNIQUE-Constraint)
- NFR-Rel-3: Order-Manager idempotent (UNIQUE-Constraint in SQLite)
- NFR-Obs-1: Strukturiertes Logging (live_loop.* Events)
- NFR-Ux-1: Deutsche CLI-Texte

Stories:
- US-P5.2: Live-Loop: Strategie empfaengt Realtime-Bars und sendet Orders

Erweitert `live/` aus Slice 5.1 um den eigentlichen Live-Loop,
ein SQLite-Trade-Journal, einen Realtime-Bar-Source und eine
`python -m quant_trader.live` CLI.

## Structure

```mermaid
classDiagram
    class LiveLoop {
        -_strategy: StrategyBase
        -_broker: BrokerClient
        -_source: RealtimeBarSource
        -_journal: TradeJournal
        -_run_id: str
        -_duration: timedelta | None
        +async run() LiveLoopSummary
    }
    class LiveLoopSummary {
        +run_id: str
        +total_signals: int
        +total_trades: int
        +total_pnl: float
    }
    class RealtimeBarSource {
        <<interface>>
        +subscribe(ticker) None
        +async next_bar() Bar
        +stop() None
    }
    class MockBarSource {
        -_subscribed: set~str~
        -_bars: deque~Bar~
        +subscribe(ticker) None
        +async next_bar() Bar
        +stop() None
        +_inject(bar) None
    }
    class IBKRBarSource {
        -_ib: IB
        -_tickers: list~str~
        +subscribe(ticker) None
        +async next_bar() Bar
        +stop() None
    }
    class TradeJournal {
        -_db_path: Path
        -_conn: Connection
        +append_open(run_id, strategy_name, ticker, action, qty, price, client_order_id, opened_at) int
        +close_trade(client_order_id, exit_price, closed_at) None
        +list_trades(run_id) list~TradeRow~
        +close() None
    }
    class TradeRow {
        +id: int
        +run_id: str
        +strategy_name: str
        +ticker: str
        +action: str
        +qty: int
        +entry_price: float | None
        +exit_price: float | None
        +pnl: float | None
        +pnl_pct: float | None
        +opened_at: str
        +closed_at: str | None
        +client_order_id: str
    }
    class LiveCLI {
        <<module>>
        +build_parser() ArgumentParser
        +main(argv) int
    }

    LiveLoop --> RealtimeBarSource
    LiveLoop --> TradeJournal
    LiveLoop --> StrategyBase
    LiveLoop --> BrokerClient
    LiveLoop --> LiveLoopSummary
    RealtimeBarSource <|.. MockBarSource
    RealtimeBarSource <|.. IBKRBarSource
    TradeJournal --> TradeRow
    LiveCLI --> LiveLoop
    LiveCLI --> TradeJournal
    LiveCLI --> BrokerFactory
```

## Flow

```mermaid
flowchart TD
    A([User: python -m quant_trader.live run --strategy X --ticker Y --broker mock]) --> B[CLI parses args]
    B --> C[build_broker settings, journal open, source build, loop build]
    C --> D[asyncio.run loop.run]
    D --> E[broker.connect falls noetig]
    E --> F[source.subscribe ticker]
    F --> G[portfolio_state = PortfolioState cash=0, positions=broker.get_positions]
    G --> H{duration abgelaufen?}
    H -->|no| I[bar = await source.next_bar]
    I --> J[strategy.on_bar bar, portfolio_state -> signals]
    J --> K{signals leer?}
    K -->|yes| H
    K -->|no| L[pro signal: order = broker.place_order]
    L --> M{order.status == FILLED?}
    M -->|no| H
    M -->|yes, BUY| N[journal.append_open run_id, strategy, ticker, BUY, qty, fill_price, client_order_id, now]
    M -->|yes, SELL| O[journal.close_trade client_order_id, fill_price, now -> pnl, pnl_pct]
    N --> H
    O --> H
    H -->|yes| P[source.stop, broker.disconnect, journal.close]
    P --> Q[log live_loop.complete]
    Q --> R([LiveLoopSummary return, Exit 0])
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant CLI as LiveCLI
    participant L as LiveLoop
    participant S as Strategy
    participant SRC as MockBarSource
    participant B as MockBroker
    participant J as TradeJournal
    participant Log as structlog

    U->>CLI: python -m quant_trader.live run --strategy sma_cross --ticker SPY --broker mock --duration 10s
    CLI->>L: LiveLoop(strategy, broker, source, journal, run_id=UUID, duration=10s)
    CLI->>L: asyncio.run(loop.run())
    L->>B: is_connected()
    B-->>L: True
    L->>SRC: subscribe(SPY)
    L->>Log: live_loop.start run_id=...
    
    loop duration abgelaufen
        L->>SRC: await next_bar()
        SRC-->>L: Bar (von _inject im Test, oder auto-generated)
        L->>S: on_bar(bar, portfolio_state)
        S-->>L: [Signal(BUY, SPY, reason)]
        L->>B: place_order(SPY, BUY, 10)
        B-->>L: Order(FILLED, 100.0, 10, client_order_id=UUID)
        L->>J: append_open(run_id, sma_cross, SPY, BUY, 10, 100.0, UUID, now)
        J-->>L: trade_id
        L->>Log: live_loop.order_placed ticker=SPY qty=10
        
        Note over L,SRC: spaeter: SELL-Signal
        L->>SRC: await next_bar()
        SRC-->>L: Bar (price=110)
        L->>S: on_bar(bar, portfolio_state)
        S-->>L: [Signal(SELL, SPY)]
        L->>B: place_order(SPY, SELL, 10)
        B-->>L: Order(FILLED, 110.0, 10, client_order_id=UUID2)
        L->>J: close_trade(client_order_id=UUID, exit_price=110, now)
        J->>J: UPDATE pnl = 10*(110-100) = 100
        L->>Log: live_loop.trade_closed ticker=SPY pnl=100
    end
    
    L->>SRC: stop()
    L->>B: disconnect()  (Mock: no-op)
    L->>J: close()
    L->>Log: live_loop.complete total_signals=N total_trades=M total_pnl=X
    L-->>CLI: LiveLoopSummary
    CLI-->>U: Exit 0
```

## Notes

- `client_order_id` UNIQUE-Constraint in SQLite garantiert Idempotenz
  (NFR-Rel-1, NFR-Rel-3) ohne Retry-Logik
- `MockBarSource._inject(bar)` ermoeglicht deterministische Tests ohne
  sleep oder random
- `IBKRBarSource` nutzt `ib_insync.IB.reqRealTimeBars()` mit 5s
  Bar-Intervall (IBKR-Limit); Polling via `ib.sleep(0)` in asyncio
  Event-Loop
- `LiveLoop.run` ist `async`; CLI ruft via `asyncio.run()`
- Bei `IBKRBroker.place_order`: nutzt `MarketOrder(action, qty)`,
  ruft `ib.placeOrder()`, wartet auf Fill via
  `ib_insync OrderState.Filled` callback (in 5.2: einfaches
  `ib.sleep(0.1)` Poll)
- `journal.append_open` kann `sqlite3.IntegrityError` werfen bei
  doppelter `client_order_id`; Loop faengt ab, loggt
  `live_loop.duplicate_order_skipped` und faehrt fort
- Backward-Compat: alle 394 bestehenden Tests unveraendert gruen
