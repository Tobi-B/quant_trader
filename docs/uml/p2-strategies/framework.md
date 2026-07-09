# UML: Slice 2.1 - Strategy Framework

Status:    DRAFT
Phase:     P2 Strategien
Slice:     2.1 Strategy Framework
Approved:  -

Mapped Requirements:
- NFR-Ux-1: klare API-Schnittstelle

Stories:
- US-P2.1: Einheitliche Strategy-Schnittstelle
- US-P2.2: Strategie-Parameter aus YAML

## Structure

```mermaid
classDiagram
    class StrategyBase {
        <<interface>>
        +name: str
        +on_bar(bar, portfolio) list~Signal~
        +warmup_bars() int
    }
    class Signal {
        +timestamp: datetime
        +ticker: str
        +action: Action
        +reason: str
    }
    class Action {
        <<enum>>
        BUY
        SELL
        HOLD
    }
    class StrategyConfig {
        +strategy_name: str
        +params: dict~str, Any~
    }
    class StrategyLoader {
        -config_path: Path
        -registry: dict~str, type~
        +register(cls) void
        +load(name: str) StrategyBase
    }

    StrategyBase ..> Signal
    Signal ..> Action
    StrategyLoader ..> StrategyConfig
    StrategyLoader ..> StrategyBase
    StrategyConfig ..> StrategyBase
```

## Flow

```mermaid
flowchart TD
    A([User: python -m quant_trader.strategies run --strategy NAME --ticker SPY]) --> B[CLI parses args]
    B --> C[StrategyLoader loads config/strategies.yaml]
    C --> D{strategy name registered?}
    D -->|no| E[Error: strategy.unknown, list available]
    E --> Z1([Exit 1])
    D -->|yes| F[StrategyLoader.load name]
    F --> G[Strategy instance with params from YAML]
    G --> H[For each bar in cache]
    H --> I{warmup done?}
    I -->|no| H
    I -->|yes| J[strategy.on_bar bar, portfolio]
    J --> K{action?}
    K -->|BUY/SELL| L[append Signal to list]
    K -->|HOLD| H
    L --> H
    H --> M{more bars?}
    M -->|yes| H
    M -->|no| N[Print signals table]
    N --> O([Exit 0])
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant CLI as SignalRunnerCLI
    participant L as StrategyLoader
    participant Y as strategies.yaml
    participant S as StrategyBase
    participant C as ParquetCache
    participant Log as structlog

    U->>CLI: run --strategy sma_cross --ticker SPY
    CLI->>L: load("sma_cross")
    L->>Y: read strategies.yaml
    Y-->>L: {sma_cross: {fast: 20, slow: 50, ...}}
    L->>L: resolve class via registry
    L-->>CLI: SmaCrossStrategy(params)
    loop for each bar in cache
        CLI->>C: read bars SPY daily
        C-->>CLI: bars
        CLI->>S: on_bar(bar, portfolio_state)
        alt warmup not done
            S-->>CLI: [] (skip)
        else warmup done
            S-->>CLI: [Signal(BUY, ...)] | [Signal(SELL, ...)] | []
        end
    end
    CLI->>Log: signal_runner.summary(strategy, count=N)
    CLI-->>U: signal table
```