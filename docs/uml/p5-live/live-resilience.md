# UML: Slice 5.3 - Live-Loop Resilience (Auto-Reconnect + Summary + Credentials)

Status:    APPROVED
Phase:     P5 Live-Trading
Slice:     5.3 Auto-Reconnect + Tageszusammenfassung + Credentials
Approved:  2026-07-14

Mapped Requirements:
- NFR-Rel-2: Live-Loop uebersteht TWS-Disconnect mit Auto-Reconnect
- NFR-Obs-2: Tageszusammenfassung als Log oder Report
- NFR-Sec-2: Broker-Credentials nur via IBKR TWS, kein persistenter Save
- NFR-Obs-1: Strukturiertes Logging (reconnect/summary Events)
- NFR-Ux-1: Deutsche Summary-Tabelle

Stories:
- US-P5.3: Live-Loop uebersteht TWS-Disconnect mit Auto-Reconnect
- US-P5.4: Tageszusammenfassung beim Beenden des Live-Loops
- US-P5.5: Broker-Credentials via TWS ohne Persistenz

Erweitert Slice 5.2 (Live-Loop + Journal + CLI) um Robustheits- und
Compliance-Features. `IBKRBroker` bleibt Stub fuer TWS-Connect,
wird aber fuer Auto-Reconnect-Tauglichkeit vorbereitet.

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
        -_reconnect_config: ReconnectConfig
        -_connected: bool
        -_monitor_task: Task | None
        +async run() LiveLoopSummary
        -_monitor_connection() None
        -_reconnect_with_backoff() None
        -_restore_subscriptions() None
        -_print_daily_summary(summary, trades) None
    }
    class ReconnectConfig {
        +initial_delay: float = 1.0
        +max_delay: float = 30.0
        +max_attempts: int = 10
    }
    class DailySummary {
        +run_id: str
        +strategy_name: str
        +total_trades: int
        +open_positions_count: int
        +total_pnl: float
        +duration_seconds: float
        +closed_at: str
    }
    class DailySummaryFormatter {
        +format(summary, trades) str
    }
    class TradeJournal {
        -_db_path: Path
        -_conn: Connection
        +append_open(...) int
        +close_trade(...) None
        +list_trades(run_id) list~TradeRow~
        +append_summary(summary) int
        +list_summaries() list~DailySummary~
        +close() None
    }
    class IBKRBroker {
        -_ib: IB
        -_host: str
        -_port: int
        -_client_id: int
        +is_connected() bool
        +place_order(...) Order
        +get_positions() dict~str,int~
        +connect() None
        +disconnect() None
    }
    class Settings {
        +reconnect_initial_delay: float = 1.0
        +reconnect_max_delay: float = 30.0
        +reconnect_max_attempts: int = 10
        +live_enabled: bool
        +ibkr_host: str
        +ibkr_port: int
        +ibkr_client_id: int
    }
    class SECURITY {
        <<docs>>
        +Credentials via TWS only (NFR-Sec-2)
        +API-Keys via .env (NFR-Sec-1)
    }

    LiveLoop --> ReconnectConfig
    LiveLoop --> DailySummary
    LiveLoop --> DailySummaryFormatter
    LiveLoop --> TradeJournal
    LiveLoop --> IBKRBroker
    LiveLoop --> Settings
    DailySummaryFormatter --> DailySummary
    TradeJournal --> DailySummary
    SECURITY ..> IBKRBroker : dokumentiert
```

## Flow

```mermaid
flowchart TD
    A([LiveLoop.run start]) --> B[Monitor-Task starten alle 5s is_connected]
    B --> C[Loop: bar -> strategy.on_bar -> signals -> orders -> journal]
    C --> D{is_connected?}
    D -->|yes| C
    D -->|no, BrokerDisconnected| E[log live_loop.broker_disconnected WARNING]
    E --> F[delay = reconnect_initial_delay]
    F --> G{attempt < max_attempts?}
    G -->|no| H[log live_loop.reconnect_failed ERROR, raise]
    G -->|yes| I[await asyncio.sleep delay]
    I --> J[broker.connect]
    J -->|Erfolg| K[log live_loop.reconnected INFO]
    J -->|Fehler| L[log reconnect_attempt_failed WARNING]
    K --> M[restore_subscriptions: source.subscribe ticker for ticker in _subscribed]
    L --> F2[delay = min delay*2, max_delay]
    M --> N[get_positions re-sync]
    F2 --> G
    N --> C
    H --> O[finally-Block: DailySummary erstellen]
    C --> P[duration abgelaufen oder KeyboardInterrupt]
    P --> O
    O --> Q[journal.append_summary]
    Q --> R[log live_loop.daily_summary]
    R --> S[print DailySummaryFormatter.format]
    S --> T([Loop beendet, Exit 0 oder 1])
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant L as LiveLoop
    participant B as IBKRBroker
    participant S as Strategy
    participant SRC as RealtimeBarSource
    participant J as TradeJournal
    participant Log as structlog

    U->>L: run()
    L->>B: connect(host, port, client_id) [TWS-Login manuell]
    B-->>L: connected
    L->>SRC: subscribe(ticker)
    L->>L: start monitor_connection background task
    L->>Log: live_loop.start run_id=...
    
    loop Loop laeuft
        L->>SRC: await next_bar()
        SRC-->>L: Bar
        L->>S: on_bar(bar, portfolio_state)
        S-->>L: [Signal]
        L->>B: place_order(...)
        B-->>L: Order(FILLED)
        L->>J: append_open(...)
        
        Note over L,B: TWS disconnectet ploetzlich
        B-->>L: is_connected() = False
        L->>Log: live_loop.broker_disconnected
        
        loop Reconnect mit Backoff
            L->>L: await asyncio.sleep(1s, dann 2s, 4s, ...)
            L->>B: connect()
            alt Erfolg
                B-->>L: connected
                L->>Log: live_loop.reconnected
                L->>SRC: restore_subscriptions (subscribe ticker)
                L->>B: get_positions() (re-sync)
            else Fehler
                B-->>L: error
                L->>Log: live_loop.reconnect_attempt_failed
            end
        end
        
        L->>S: on_bar(...)  # Loop laeuft weiter
    end
    
    U->>L: Ctrl-C (KeyboardInterrupt)
    L->>L: finally-Block
    L->>J: trades = list_trades(run_id)
    L->>J: append_summary(DailySummary run_id, strategy, N, open, pnl, duration, closed_at)
    L->>Log: live_loop.daily_summary
    L->>U: print DailySummaryFormatter.format (deutsche Tabelle)
    L-->>U: Exit 130 (KeyboardInterrupt)
```

## Notes

- **Auto-Reconnect nur fuer IBKRBroker**: `MockBroker.is_connected()`
  returnt immer True, daher kein Reconnect noetig
- **Exponential-Backoff**: `1s -> 2s -> 4s -> 8s -> 16s -> 30s` (cap),
  max 10 Attempts
- **Subscription-Recovery**: `MockBarSource._subscribed` (set) +
  `IBKRBarSource._tickers` (list) werden bei Reconnect re-subscribed
- **DailySummary in `finally`-Block**: wird auch bei KeyboardInterrupt
  und Reconnect-Failure geschrieben
- **Credentials via TWS**: `IBKRBroker.connect()` ruft `ib.connect()`
  ohne Credentials-Argumente; TWS-Login-Prompt manuell am TWS
- **SECURITY.md**: zentrale Doku der Credentials-Policy (NFR-Sec-1 +
  NFR-Sec-2)
- **Backward-Compat**: alle 417 bestehenden Tests unveraendert gruen
  (Defaults der neuen Reconnect-Config = sinnvolle Werte, MockBroker
  uebergeht Reconnect-Path)
