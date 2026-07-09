# UML: Slice 2.3 - Mean-Reversion (RSI)

Status:    DRAFT
Phase:     P2 Strategien
Slice:     2.3 Mean-Reversion (RSI)
Approved:  -

Mapped Requirements:
- NFR-Perf-2: schnelle Berechnung

Stories:
- US-P2.5: RSI Mean-Reversion

## Structure

```mermaid
classDiagram
    class StrategyBase {
        <<interface>>
        +name: str
        +on_bar(bar, portfolio) list~Signal~
        +warmup_bars() int
    }
    class RsiMeanReversionStrategy {
        -period: int
        -oversold: float
        -overbought: float
        -prev_rsi: float
        +name: str = "rsi_mean_reversion"
        +on_bar(bar, portfolio) list~Signal~
        +warmup_bars() int
        -_compute_rsi() float
    }

    StrategyBase <|-- RsiMeanReversionStrategy
```

## Flow

```mermaid
flowchart TD
    A([on_bar bar]) --> B[append close to window]
    B --> C{window size >= period+1?}
    C -->|no| D[return empty - warmup]
    C -->|yes| E[compute gains and losses over period]
    E --> F[avg_gain, avg_loss]
    F --> G{rsi = 100 - 100 / 1 + rs?}
    G --> H[update prev_rsi, return empty if no crossing]
    H --> I{rsi crosses oversold from above?}
    I -->|yes| J[BUY signal: reason=rsi_oversold_cross]
    I -->|no| K{rsi crosses overbought from below?}
    K -->|yes| L[SELL signal: reason=rsi_overbought_cross]
    K -->|no| M[return empty - no crossing]
    J --> N([return signals])
    L --> N
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant CLI as SignalRunnerCLI
    participant S as RsiMeanReversionStrategy
    participant Log as structlog

    U->>CLI: run --strategy rsi_mean_reversion --ticker SPY
    CLI->>S: instance with period=14, oversold=30, overbought=70
    loop for each bar in cache
        CLI->>S: on_bar(bar, portfolio_state)
        alt warmup not done (need period+1 bars)
            S-->>CLI: []
        else RSI computed
            S->>S: prev_rsi stored
            alt rsi crosses oversold
                S-->>CLI: [Signal(BUY, reason=rsi_oversold_cross)]
            else rsi crosses overbought
                S-->>CLI: [Signal(SELL, reason=rsi_overbought_cross)]
            else no crossing
                S-->>CLI: []
            end
        end
    end
    CLI->>Log: signal_runner.summary(strategy, count=N)
    CLI-->>U: table of signals
```