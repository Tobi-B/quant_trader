# UML: Slice 2.4 - ETF-Rotation (Top-N Momentum)

Status:    APPROVED
Phase:     P2 Strategien
Slice:     2.4 ETF-Rotation
Approved:  2026-07-10 (User)

Mapped Requirements:
- NFR-Perf-2: schnelle Berechnung (auch ueber mehrere ETFs)

Stories:
- US-P2.6: ETF Top-N Momentum Rotation

Hinweis: Diese Strategie arbeitet universe-basiert. on_bar bekommt einen Universe-Snapshot
(Ticker -> Bar), nicht einen einzelnen Bar. Daher erweitern wir StrategyBase optional um
eine zweite Methode `on_universe_bars(date, bars_by_ticker, portfolio)`.

## Structure

```mermaid
classDiagram
    class StrategyBase {
        <<interface>>
        +name: str
        +on_bar(bar, portfolio) list~Signal~
        +warmup_bars() int
    }
    class MultiTickerStrategyBase {
        <<interface>>
        +on_universe_bars(date, bars_by_ticker, portfolio) list~Signal~
        +warmup_bars() int
    }
    class EtfRotationStrategy {
        -universe: list~str~
        -top_n: int
        -lookback_days: int
        -rebalance_freq: str = "monthly"
        -last_rebalance: date
        +name: str = "etf_rotation"
        +on_universe_bars(date, bars_by_ticker, portfolio) list~Signal~
        +warmup_bars() int
    }

    StrategyBase <|-- EtfRotationStrategy
    MultiTickerStrategyBase <|-- EtfRotationStrategy
```

## Flow

```mermaid
flowchart TD
    A([on_universe_bars date, bars_by_ticker, portfolio]) --> B{warmup done?}
    B -->|no| C[return empty - need N days of prices for all tickers]
    B -->|yes| D{rebalance day today?}
    D -->|no| E[return empty - hold positions]
    D -->|yes| F[compute lookback return for each ticker]
    F --> G[rank tickers by return desc]
    G --> H{any positive return?}
    H -->|no| I[SELL all holdings, weight to CASH]
    H -->|yes| J[select top-N tickers]
    J --> K{for each current holding?}
    K -->|not in top-N| L[emit SELL]
    K -->|in top-N| M[keep - no signal]
    L --> N{for each top-N not held?}
    M --> N
    N -->|not held| O[emit BUY with weight 1/N]
    N -->|all held| P[return signals]
    O --> P
    I --> P
```

## Sequence

```mermaid
sequenceDiagram
    participant CLI as SignalRunnerCLI
    participant S as EtfRotationStrategy
    participant W as WindowStore
    participant R as Ranker
    participant P as Portfolio

    Note over CLI: monthly rebalance trigger
    CLI->>S: on_universe_bars(date, {ticker: bar, ...}, portfolio)
    S->>W: get returns over lookback for each ticker
    W-->>S: {SPY: 0.05, AGG: -0.01, TLT: 0.02, ...}
    S->>R: rank descending
    R-->>S: ordered list of tickers
    alt all non-positive returns
        S->>P: holdings -> []
        S-->>CLI: [SELL(SPY), SELL(AGG), ...]
    else top_n identified
        loop for each current holding not in top_n
            S-->>CLI: SELL(ticker)
        end
        loop for each top_n not held
            S-->>CLI: BUY(ticker, weight=1/N)
        end
    end
```