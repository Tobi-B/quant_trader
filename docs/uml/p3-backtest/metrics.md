# UML: Slice 3.2 - Metrics

Status:    DRAFT
Phase:     P3 Backtest
Slice:     3.2 Metrics
Approved:  -

Mapped Requirements:
- NFR-Perf-1: schnelle Berechnung (<30s fuer 5 Jahre Daily)
- NFR-Data-2: Adj. Close fuer Rueckrechnungen

Stories:
- US-P3.3: Backtest-Metriken berechnen

## Structure

```mermaid
classDiagram
    class MetricsCalculator {
        +calculate(result: BacktestResult) Metrics
    }
    class Metrics {
        +total_return_pct: float
        +cagr_pct: float
        +sharpe_ratio: float | None
        +max_drawdown_pct: float
        +win_rate_pct: float | None
        +n_trades: int
        +exposure_pct: float
    }
    class EquityCurveStats {
        +compute_returns(equity_curve) list~float~
        +cagr(equity_curve) float
        +sharpe(returns, rf=0, periods=252) float
        +max_drawdown(equity_curve) float
        +exposure(snapshots) float
    }
    class TradeStats {
        +win_rate(trades) float | None
        +total_pnl(trades) float
        +avg_pnl(trades) float
    }

    MetricsCalculator --> EquityCurveStats
    MetricsCalculator --> TradeStats
    MetricsCalculator --> Metrics
```

## Flow

```mermaid
flowchart TD
    A([BacktestResult]) --> B[MetricsCalculator.calculate]
    B --> C[EquityCurveStats.compute_returns daily pct changes]
    C --> D[EquityCurveStats.cagr equity, days]
    D --> E[EquityCurveStats.sharpe mean/std, rf=0, periods=252]
    E --> F[EquityCurveStats.max_drawdown Peak-to-Trough]
    F --> G[EquityCurveStats.exposure snapshot positions != 0]
    G --> H[TradeStats.win_rate trades won / total]
    H --> I{trades < 2?}
    I -->|yes| J[set win_rate, sharpe = None]
    I -->|no| K[compute normally]
    J --> L[Build Metrics dataclass]
    K --> L
    L --> M([Metrics: Total Return, CAGR, Sharpe, MDD, Win-Rate, N-Trades, Exposure])
```

## Sequence

```mermaid
sequenceDiagram
    participant CLI as BacktestCLI
    participant Calc as MetricsCalculator
    participant ECS as EquityCurveStats
    participant TS as TradeStats

    CLI->>Calc: calculate(BacktestResult)
    Calc->>ECS: compute_returns(equity_curve)
    ECS-->>Calc: list[float] (daily returns)
    Calc->>ECS: cagr(equity_curve)
    ECS-->>Calc: float
    Calc->>ECS: sharpe(returns, rf=0, periods=252)
    ECS-->>Calc: float | None
    Calc->>ECS: max_drawdown(equity_curve)
    ECS-->>Calc: float
    Calc->>ECS: exposure(snapshots)
    ECS-->>Calc: float (0-100)
    alt trades >= 2
        Calc->>TS: win_rate(trades)
        TS-->>Calc: float (0-100)
    else trades < 2
        Calc->>Calc: win_rate = None, sharpe = None
    end
    Calc-->>CLI: Metrics
```