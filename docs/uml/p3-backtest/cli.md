# UML: Slice 3.4 - Backtest CLI

Status:    APPROVED
Phase:     P3 Backtest
Slice:     3.4 CLI
Approved:  2026-07-14

Mapped Requirements:
- NFR-Ux-1: CLI-Texte deutsch
- NFR-Obs-1: Strukturiertes Logging

Stories:
- US-P3.8: Backtest ueber CLI starten

## Structure

```mermaid
classDiagram
    class BacktestCLI {
        +main(argv) int
        +build_parser() ArgumentParser
    }
    class BacktestCommand {
        +execute(args) int
    }
    class ListCommand {
        +execute(args) int
    }
    class RunArgs {
        +strategy: str
        +ticker: str
        +universe: str | None
        +start: date
        +end: date
        +granularity: Granularity
        +fill_mode: FillMode
        +initial_cash: float
        +no_report: bool
    }
    class RunId {
        +generate() str
    }
    class BacktestOrchestrator {
        +run(args) BacktestResult
    }

    BacktestCLI --> BacktestCommand
    BacktestCLI --> ListCommand
    BacktestCommand --> RunArgs
    BacktestCommand --> BacktestOrchestrator
    BacktestCommand --> RunId
```

## Flow

```mermaid
flowchart TD
    A([User: python -m quant_trader.backtest run --strategy X ...]) --> B[CLI parses args]
    B --> C{command == run?}
    C -->|no, list| D[ListCommand.execute list reports/]
    D --> E[print table of runs]
    E --> P([Exit 0])
    C -->|yes| F[Resolve strategy + ticker/universe via existing runners]
    F --> G[Load bars from cache]
    G --> H[BacktestOrchestrator.run BacktestEngine + Metrics + Report]
    H --> I{strategy/cache ok?}
    I -->|no, unknown strategy| J[log + Exit 1]
    I -->|no, cache missing| K[log + Exit 1]
    I -->|yes| L{--no-report?}
    L -->|no| M[ReportBuilder.build output files]
    L -->|yes| N[ConsoleFormatter only]
    M --> O[print console output]
    N --> O
    O --> P
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant CLI as BacktestCLI
    participant SR as SignalRunner
    participant Cache as ParquetCache
    participant BE as BacktestEngine
    participant MC as MetricsCalculator
    participant RB as ReportBuilder
    participant Log as structlog

    U->>CLI: run --strategy sma_cross --ticker SPY --fill-mode next_open --initial-cash 50000
    CLI->>SR: run(strategy_name, ticker, start, end)
    SR->>Cache: read(SPY, daily, start, end)
    Cache-->>SR: bars
    SR-->>CLI: bars
    CLI->>BE: run(strategy, bars, BacktestConfig fill_mode, initial_cash)
    BE->>Log: backtest.start
    BE->>BE: process bars + signals + fills
    BE->>Log: backtest.complete
    BE-->>CLI: BacktestResult
    CLI->>MC: calculate(result)
    MC-->>CLI: Metrics
    alt --no-report not set
        CLI->>RB: build(result, reports/<run-id>/)
        RB-->>CLI: ReportPaths
    end
    CLI-->>U: Console-Tabelle + Paths
```