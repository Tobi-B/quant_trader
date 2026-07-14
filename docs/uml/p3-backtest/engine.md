# UML: Slice 3.1 - Backtest Engine Core

Status:    DRAFT
Phase:     P3 Backtest
Slice:     3.1 Engine Core
Approved:  -

Mapped Requirements:
- NFR-Perf-1: 5 Jahre Daily < 30s
- NFR-Obs-1: Strukturiertes Logging
- NFR-Data-1: Parquet-Cache als Source

Stories:
- US-P3.1: Strategie auf historische Daten backtesten
- US-P3.2: Equal-Weight Position-Sizing

## Structure

```mermaid
classDiagram
    class BacktestEngine {
        +run(strategy, bars_by_ticker, config) BacktestResult
        -_pending_fills: list~PendingFill~
        -_portfolio: Portfolio
        -_strategy: StrategyBase
    }
    class Portfolio {
        +cash: float
        +positions: dict~str,int~
        +equity(prices) float
        +apply_fill(fill)
    }
    class PositionSizer {
        <<interface>>
        +allocate(price, available_cash, n_open_positions) SizingResult
    }
    class EqualWeightSizer {
        +allocate(...) SizingResult
    }
    class FillSimulator {
        +simulate(signal, next_bar) Fill
    }
    class FillMode {
        <<enum>>
        NEXT_OPEN
        SAME_CLOSE
    }
    class PendingFill {
        +signal: Signal
        +execute_on: Bar
    }
    class Fill {
        +ticker: str
        +price: float
        +qty: int
        +fee: float
    }
    class SizingResult {
        +qty: int
        +allocated_cash: float
        +skipped: bool
    }
    class BacktestConfig {
        +initial_cash: float
        +fill_mode: FillMode
        +sizer: PositionSizer
    }
    class BacktestResult {
        +trades: list~Trade~
        +equity_curve: list~EquitySnapshot~
        +final_equity: float
    }
    class Trade {
        +ticker: str
        +entry_date: datetime
        +entry_price: float
        +exit_date: datetime
        +exit_price: float
        +pnl: float
    }
    class EquitySnapshot {
        +date: date
        +equity: float
        +cash: float
        +positions: dict~str,int~
    }

    BacktestEngine --> Portfolio
    BacktestEngine --> PositionSizer
    BacktestEngine --> FillSimulator
    BacktestEngine --> PendingFill
    BacktestEngine --> BacktestConfig
    BacktestEngine --> BacktestResult
    PositionSizer <|.. EqualWeightSizer
    FillSimulator --> Fill
    FillSimulator --> FillMode
    Portfolio --> Fill
    BacktestResult --> Trade
    BacktestResult --> EquitySnapshot
```

## Flow

```mermaid
flowchart TD
    A([User: python -m quant_trader.backtest run --strategy X ...]) --> B[Load strategy + bars from cache]
    B --> C[Build BacktestConfig: initial_cash, fill_mode, sizer]
    C --> D{Strategy type?}
    D -->|single| E[iterate bars chronologically]
    D -->|multi| F[group bars by date, iterate by date]
    E --> G[for each bar: strategy.on_bar -> signals]
    F --> G
    G --> H[append signals to _pending_fills]
    H --> I[for each pending_fill whose execute_on <= current_bar]
    I --> J{Fill-Mode}
    J -->|NEXT_OPEN| K[fill_price = current_bar.open]
    J -->|SAME_CLOSE| L[fill_price = signal_bar.close]
    K --> M[Sizer.allocate available_cash, n_positions]
    L --> M
    M --> N{cash > 0?}
    N -->|no| O[log backtest.insufficient_cash, skip]
    N -->|yes| P{Action}
    P -->|BUY| Q[Portfolio.open qty]
    P -->|SELL| R[Portfolio.close position]
    P -->|HOLD| S[noop]
    Q --> T[EquitySnapshot date, equity cash positions]
    R --> T
    T --> U{more bars?}
    U -->|yes| G
    U -->|no| V[Build BacktestResult trades, equity_curve]
    V --> W[log backtest.complete duration, bars, trades]
    W --> X([Exit 0 + return BacktestResult])
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant CLI as BacktestCLI
    participant E as BacktestEngine
    participant S as Strategy
    participant Sim as FillSimulator
    participant Sz as EqualWeightSizer
    participant P as Portfolio
    participant Log as structlog

    U->>CLI: run --strategy sma_cross --ticker SPY
    CLI->>E: run(strategy, bars, BacktestConfig)
    E->>Log: backtest.start(strategy, ticker, bars_count)
    loop for each bar
        E->>S: on_bar(bar, portfolio_snapshot)
        S-->>E: [Signal]
        loop for each signal
            E->>Sim: simulate(signal, next_bar, mode)
            Sim-->>E: Fill
            alt BUY
                E->>Sz: allocate(price, cash, n_positions)
                Sz-->>E: SizingResult(qty=N)
                E->>P: apply_fill(BUY, qty)
            else SELL
                E->>P: apply_fill(SELL, current_qty)
            end
            P-->>E: updated cash, positions
            E->>E: append EquitySnapshot
        end
    end
    E->>Log: backtest.complete(duration, trades)
    E-->>CLI: BacktestResult
    CLI-->>U: Console-Tabelle + Files
```

## State Machine: Position

```mermaid
stateDiagram-v2
    [*] --> Flat
    Flat --> Long: BUY fill
    Long --> Long: re-buy (no-op)
    Long --> Flat: SELL fill (full close)
    Long --> Flat: rebalance drop
    Flat --> Flat: SELL (no-op, warn-log)
    state Long {
        [*] --> Building
        Building --> Held: 1+ fill
        Held --> Held: subsequent bars
    }
```

## UML-Notes

- `Portfolio` ist immutable snapshot per Bar (frozen dataclass mit `positions: dict[str, int]`).
- `PendingFill` ermoeglicht NEXT_OPEN-Modus ohne Look-Ahead.
- `PositionSizer` ist Interface; Slice 3.1 implementiert nur `EqualWeightSizer`.
- `BacktestResult` ist Input fuer Slice 3.2 (Metrics) und 3.3 (Report).