# UML: Slice 2.2 - Trend-Strategien (SMA-Cross + Momentum)

Status:    APPROVED
Phase:     P2 Strategien
Slice:     2.2 Trend-Strategien
Approved:  2026-07-10

Mapped Requirements:
- NFR-Perf-2: schnelle Berechnung

Stories:
- US-P2.3: SMA-Crossover
- US-P2.4: Momentum 12-1

Hinweis: zwei Strategien in einem Slice, gleiches Pattern. Structure zeigt beide als StrategyBase-Subklassen.

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
        +name: str
        +on_universe_bars(date, bars_by_ticker, portfolio) list~Signal~
        +warmup_bars() int
    }
    class SmaCrossStrategy {
        -fast_period: int
        -slow_period: int
        +name: str = "sma_cross"
        +on_bar(bar, portfolio) list~Signal~
        +warmup_bars() int
    }
    class MomentumStrategy {
        -lookback_months: int
        -skip_recent_months: int
        -top_n: int
        -universe: list~str~
        +name: str = "momentum"
        +on_universe_bars(date, bars_by_ticker, portfolio) list~Signal~
        +warmup_bars() int
    }
    class Signal {
        +timestamp: datetime
        +ticker: str
        +action: Action
        +reason: str
    }

    StrategyBase <|-- SmaCrossStrategy
    MultiTickerStrategyBase <|-- MomentumStrategy
    SmaCrossStrategy ..> Signal
    MomentumStrategy ..> Signal
```

## Flow (SMA-Cross)

```mermaid
flowchart TD
    A([on_bar bar]) --> B[append close to window]
    B --> C{window size >= slow_period?}
    C -->|no| D[return empty - warmup]
    C -->|yes| E[fast_sma = mean last fast_period]
    E --> F[slow_sma = mean last slow_period]
    F --> G{prev_fast_sma and prev_slow_sma exist?}
    G -->|no| H[save current, return empty]
    G -->|yes| I{fast_sma > slow_sma AND prev_fast_sma <= prev_slow_sma?}
    I -->|yes| J[BUY signal: reason=sma_cross_up]
    I -->|no| K{fast_sma < slow_sma AND prev_fast_sma >= prev_slow_sma?}
    K -->|yes| L[SELL signal: reason=sma_cross_down]
    K -->|no| M[return empty - no crossing]
    H --> N[save current SMAs as prev]
    J --> N
    L --> N
    N --> O([return signals])
```

## Sequence (Momentum 12-1)

```mermaid
sequenceDiagram
    participant S as MomentumStrategy
    participant W as WindowStore
    participant R as Ranker

    Note over S: monthly anchor (e.g. last bar of month)
    S->>W: performance for each ticker in universe over 12 months (skip last month)
    W-->>S: {ticker: return_pct, ...}
    S->>R: rank by performance descending
    R-->>S: ordered list of tickers
    alt current_holdings not in top_n
        S->>S: emit SELL for each drop-out
        S->>S: emit BUY for each new top_n entry
    else no change
        S-->>S: return empty
    end
```

Hinweis Momentum-Strategie arbeitet auf einem Universum von Bars, der SignalRunner
muss alle Ticker laden und reihen. Daher erbt `MomentumStrategy` von
`MultiTickerStrategyBase` (Slice 2.1) statt von `StrategyBase`; der Runner in
Slice 2.5 orchestriert den Aufruf von `on_universe_bars(date, bars_by_ticker, portfolio)`.