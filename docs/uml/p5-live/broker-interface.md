# UML: Slice 5.1 - Broker Interface + Mock + Order

Status:    APPROVED
Phase:     P5 Live-Trading
Slice:     5.1 Broker Interface + Mock + Order
Approved:  2026-07-14

Mapped Requirements:
- NFR-Rel-3: Order-Manager idempotent (UUID client_order_id)
- NFR-Sec-2: Credentials via TWS only (out-of-scope fuer 5.1, kommt in 5.5)
- NFR-Obs-1: Strukturiertes Logging (broker.order_placed, broker.order_filled, broker.order_rejected)

Stories:
- US-P5.1: Strategie sendet Market-Order ueber Broker-Abstraktion

Schafft die Foundation fuer Phase 5: ein einheitliches `BrokerClient`
Protocol, das sowohl `MockBroker` (CI, deterministisch) als auch
`IBKRBroker` (real, slice 5.2) implementiert. `Order` und
`OrderStatus` sind die geteilte Sprache.

## Structure

```mermaid
classDiagram
    class BrokerClient {
        <<interface>>
        +is_connected() bool
        +place_order(ticker, action, qty) Order
        +get_positions() dict~str,int~
        +cancel_order(client_order_id) bool
    }
    class MockBroker {
        -_orders: dict~str, Order~
        -_positions: dict~str, int~
        -_fill_price: float
        +is_connected() bool
        +place_order(ticker, action, qty) Order
        +get_positions() dict~str,int~
        +cancel_order(client_order_id) bool
        -_execute(order) Order
        -_with_status(order, **changes) Order
    }
    class IBKRBroker {
        -_host: str
        -_port: int
        -_client_id: int
        -_ib: IB
        +is_connected() bool
        +place_order(ticker, action, qty) Order
        +get_positions() dict~str,int~
        +cancel_order(client_order_id) bool
    }
    class BrokerFactory {
        <<module>>
        +build_broker(settings) BrokerClient
    }
    class Order {
        +id: str
        +client_order_id: str
        +ticker: str
        +action: Action
        +qty: int
        +type: OrderType
        +status: OrderStatus
        +filled_qty: int
        +avg_fill_price: float | None
        +created_at: datetime
        +updated_at: datetime
    }
    class OrderStatus {
        <<enum>>
        PENDING
        SUBMITTED
        FILLED
        CANCELLED
        REJECTED
    }
    class OrderType {
        <<enum>>
        MARKET
        LIMIT
    }
    class Action {
        <<enum>>
        BUY
        SELL
        HOLD
    }
    class Settings {
        +live_enabled: bool = False
        +ibkr_host: str = "127.0.0.1"
        +ibkr_port: int = 7497
        +ibkr_client_id: int = 1
        +mock_fill_price: float = 100.0
    }

    BrokerClient <|.. MockBroker
    BrokerClient <|.. IBKRBroker
    BrokerFactory --> MockBroker
    BrokerFactory --> IBKRBroker
    BrokerFactory --> Settings
    MockBroker --> Order
    IBKRBroker --> Order
    Order --> OrderStatus
    Order --> OrderType
    Order --> Action
```

## Flow

```mermaid
flowchart TD
    A([Strategy emits Signal BUY]) --> B[broker.place_order ticker, action, qty]
    B --> C{Factory.build_broker settings}
    C -->|live_enabled=False| D[MockBroker]
    C -->|live_enabled=True| E[IBKRBroker]
    D --> F{qty > 0?}
    F -->|no| G[Order status=REJECTED]
    F -->|yes| H[Order status=SUBMITTED, client_order_id=UUID]
    H --> I[_execute synchron]
    I --> J[Status -> FILLED, filled_qty=qty, avg_fill_price=fill_price]
    J --> K[Update _positions ticker -> qty]
    K --> L[log broker.order_filled]
    G --> M[log broker.order_rejected]
    L --> N([return Order])
    M --> N
    E --> O[Stub in Slice 5.1: NotImplementedError, in 5.2 ib_insync.MarketOrder]
    O --> P([Vollstaendig in Slice 5.2])
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User / Strategie
    participant F as BrokerFactory
    participant MB as MockBroker
    participant Log as structlog

    U->>F: build_broker(settings live_enabled=False)
    F->>MB: MockBroker(fill_price=settings.mock_fill_price)
    F-->>U: BrokerClient (MockBroker)

    U->>MB: place_order(SPY, BUY, 10)
    MB->>Log: broker.order_placed ticker=SPY qty=10 client_order_id=UUID
    MB->>MB: Order status=SUBMITTED, created_at=now
    MB->>MB: _execute(order)
    MB->>MB: avg_fill_price=100.0, status=FILLED, filled_qty=10
    MB->>MB: _positions[SPY] += 10
    MB->>Log: broker.order_filled ticker=SPY qty=10 price=100.0
    MB-->>U: Order(FILLED, 100.0, 10, ...)

    U->>MB: get_positions()
    MB-->>U: {SPY: 10}

    U->>MB: cancel_order(UUID)
    MB-->>U: False (already FILLED)

    U->>MB: place_order(SPY, BUY, 0)
    MB->>Log: broker.order_rejected qty=0
    MB-->>U: Order(REJECTED, ...)
```

## Notes

- `Order` ist frozen; Status-Updates erzeugen neue Instanzen
  (`_with_status(order, status=FILLED, ...)` Helper in `MockBroker`).
- `client_order_id` ist UUID (Idempotenz, NFR-Rel-3).
- `IBKRBroker` ist in Slice 5.1 ein Stub mit `NotImplementedError` und
  Slice-5.2-Hinweis; echte `ib_insync`-Logik kommt in 5.2.
- `MockBroker` ist deterministisch: `fill_price` aus Settings, kein
  Random, kein Time-Sleep, kein Network -> CI ohne `live` extra.
- `ib_insync`-Import nur in `ibkr.py` mit `try/except ImportError ->
  SystemExit`. So funktioniert CI ohne `live` extra.
- `OrderType.LIMIT` ist im Enum, wird aber in P5 nicht genutzt
  (nur MARKET). Erweiterung in spaeterer Phase.
