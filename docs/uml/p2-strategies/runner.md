# UML: Slice 2.5 - Signal-Runner CLI

Status:    APPROVED
Phase:     P2 Strategien
Slice:     2.5 Signal-Runner
Approved:  2026-07-14

Mapped Requirements:
- NFR-Obs-1: Strukturierte Logs
- NFR-Data-1: Parquet-Cache nutzen

Stories:
- US-P2.7: Strategie-Signale ohne Backtest ausgeben

## Structure

```mermaid
classDiagram
    class SignalRunnerCLI {
        +main(argv) int
    }
    class StrategyLoader {
        -config_path: Path
        +load(name) StrategyBase
    }
    class ParquetCache {
        +read(ticker, granularity, start, end) list~Bar~
    }
    class StrategyBase {
        <<interface>>
        +on_bar(bar, portfolio) list~Signal~
    }
    class MultiTickerStrategyBase {
        <<interface>>
        +on_universe_bars(date, bars_by_ticker, portfolio) list~Signal~
    }
    class SignalFormatter {
        +format_signals(signals, limit) str
    }
    class PortfolioState {
        +cash: float
        +positions: dict~str, int~
    }

    SignalRunnerCLI --> StrategyLoader
    SignalRunnerCLI --> ParquetCache
    SignalRunnerCLI --> SignalFormatter
    SignalRunnerCLI --> StrategyBase
    SignalRunnerCLI --> MultiTickerStrategyBase
    StrategyLoader ..> StrategyBase
```

## Flow

```mermaid
flowchart TD
    A([User: python -m quant_trader.strategies run --strategy NAME --ticker SPY ...]) --> B[CLI parses args]
    B --> C{strategy is multi-ticker?}
    C -->|yes| D[load universe tickers from preset or --universe]
    D --> E[read bars for all tickers]
    E --> F[group bars by date]
    C -->|no| G[read bars for --ticker]
    G --> H[iterate bars chronologically]
    F --> H
    H --> I{multi-ticker strategy?}
    I -->|yes| J[strategy.on_universe_bars date, bars, portfolio]
    I -->|no| K[strategy.on_bar bar, portfolio]
    J --> L[collect signals]
    K --> L
    L --> H
    H --> M[format signals via SignalFormatter, max 100]
    M --> N[print table to stdout]
    N --> O[log summary count signals]
    O --> P([Exit 0])
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant CLI as SignalRunnerCLI
    participant L as StrategyLoader
    participant C as ParquetCache
    participant S as Strategy
    participant F as SignalFormatter
    participant Log as structlog

    U->>CLI: run --strategy sma_cross --ticker SPY --start ... --end ...
    CLI->>L: load("sma_cross")
    L-->>CLI: SmaCrossStrategy
    CLI->>C: read(SPY, daily, start, end)
    C-->>CLI: bars
    CLI->>Log: signal_runner.start(strategy=sma_cross, ticker=SPY)
    loop for each bar
        CLI->>S: on_bar(bar, portfolio)
        S-->>CLI: [] | [Signal]
        CLI->>CLI: collect signals
    end
    CLI->>F: format_signals(signals, limit=100)
    F-->>CLI: text table
    CLI->>Log: signal_runner.summary(strategy, count)
    CLI-->>U: print(table)
```