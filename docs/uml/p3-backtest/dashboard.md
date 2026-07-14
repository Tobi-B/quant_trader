# UML: Slice 3.5 - Interaktives Backtest-Dashboard (Run-Trigger)

Status:    APPROVED
Phase:     P3 Backtest
Slice:     3.5 Interaktives Backtest-Dashboard
Approved:  2026-07-14

Mapped Requirements:
- NFR-Ux-1: UI-Texte deutsch, klare Fehlermeldungen
- NFR-Obs-1: Strukturiertes Logging waehrend des Runs
- NFR-Perf-1: <30s fuer 5y Daily (gilt fuer UI-getriggerte Runs)
- NFR-Data-1: Parquet-Cache wird ueber bestehende DataProvider genutzt

Stories:
- US-P3.9: Backtest aus dem Dashboard starten

Erweitert Slice 3.3 (Streamlit-Dashboard) um einen Run-Trigger.
Bestehende Klassen `BacktestDashboard`, `ReportLoader`, `EquityPlot`,
`DrawdownIndicator` aus `docs/uml/p3-backtest/report.md` werden wiederverwendet.

## Structure

```mermaid
classDiagram
    class BacktestDashboard {
        +render() None
    }
    class RunForm {
        +render_sidebar(registry, universe_presets) RunFormState
    }
    class RunFormState {
        +strategy_name: str
        +ticker: str
        +universe_preset: str | None
        +start: date
        +end: date
    }
    class DashboardRunner {
        -_running: bool
        +run_request(state: RunFormState) BacktestReport
    }
    class RunProgress {
        +show_spinner() None
        +stream_logs(log_buffer) None
        +mark_complete(report) None
        +mark_error(message: str) None
    }
    class ResultsView {
        +render_metrics_table(metrics) None
        +render_equity_curve(report) None
        +render_top_trades(report) None
    }
    class BacktestOrchestrator {
        +run(args) BacktestResult
    }
    class ReportBuilder {
        +build(result, output_dir) ReportPaths
    }
    class ReportLoader {
        +list_runs(reports_dir) list~RunSummary~
        +load_run(run_id) BacktestReport
    }
    class StrategyRegistry {
        +list_names() list~str~
        +get(name) StrategyBase
    }
    class UniverseLoader {
        +load(name) list~str~
    }
    class ParquetCache {
        +read(ticker, granularity, start, end) list~Bar~
    }

    BacktestDashboard --> RunForm
    BacktestDashboard --> DashboardRunner
    BacktestDashboard --> RunProgress
    BacktestDashboard --> ResultsView
    BacktestDashboard --> ReportLoader
    RunForm --> RunFormState
    DashboardRunner --> BacktestOrchestrator
    DashboardRunner --> ReportBuilder
    DashboardRunner --> RunProgress
    DashboardRunner --> ParquetCache
    DashboardRunner --> StrategyRegistry
    DashboardRunner --> UniverseLoader
    ResultsView --> ReportLoader
    BacktestOrchestrator --> ParquetCache
```

## Flow

```mermaid
flowchart TD
    A([User: streamlit run scripts/backtest_dashboard.py]) --> B[BacktestDashboard.render]
    B --> C[RunForm.render_sidebar: Strategie + Ticker/Universe + Start + End]
    C --> D{User klickt 'Backtest starten'?}
    D -->|no| C
    D -->|yes| E[Button disabled, DashboardRunner.run_request]
    E --> F[StrategyRegistry.get name]
    F --> G{Strategy bekannt?}
    G -->|no| H[RunProgress.mark_error 'Unbekannte Strategie']
    H --> C
    G -->|yes| I[UniverseLoader.load preset OR Ticker]
    I --> J[ParquetCache.read bars]
    J --> K{Cache vorhanden?}
    K -->|no| L[RunProgress.mark_error 'Cache fehlt, bitte make data']
    L --> C
    K -->|yes| M[RunProgress.show_spinner + stream_logs]
    M --> N[BacktestOrchestrator.run mit Defaults: next_open, 100k, daily]
    N --> O[MetricsCalculator + ReportBuilder.build reports/run-id/]
    O --> P[RunProgress.mark_complete]
    P --> Q[ResultsView: Metrics-Tabelle + Equity-Curve + Top-Trades]
    Q --> R([User sieht Ergebnis im selben Tab])
    R --> C

    S([User wechselt zu Read-Mode US-P3.7]) --> T[ReportLoader.list_runs]
    T --> U[ReportLoader.load_run]
    U --> V[ResultsView render]
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant D as BacktestDashboard
    participant F as RunForm
    participant R as StrategyRegistry
    participant UL as UniverseLoader
    participant DR as DashboardRunner
    participant BE as BacktestEngine
    participant MC as MetricsCalculator
    participant RB as ReportBuilder
    participant RP as RunProgress
    participant RV as ResultsView
    participant Log as structlog

    U->>D: oeffnet Browser
    D->>F: render_sidebar
    F->>R: list_names
    R-->>F: ['sma_cross', 'momentum', 'rsi_mean_reversion', 'etf_rotation']
    F-->>U: Sidebar mit Dropdowns + Date-Inputs

    U->>F: Strategie + Ticker + Start/End + Klick 'Backtest starten'
    F-->>DR: run_request(RunFormState)
    DR->>RP: show_spinner
    DR->>R: get('sma_cross')
    R-->>DR: StrategyBase
    DR->>UL: load('sp500')  alt Ticker-Fall: skip
    UL-->>DR: tickers
    DR->>BE: run(strategy, bars, BacktestConfig defaults)
    BE->>Log: backtest.start
    BE->>RP: stream_logs (progress callback)
    BE->>Log: backtest.complete
    BE-->>DR: BacktestResult
    DR->>MC: calculate(result)
    MC-->>DR: Metrics
    DR->>RB: build(result, reports/<run-id>/)
    RB-->>DR: ReportPaths
    DR->>RP: mark_complete
    DR-->>D: BacktestReport

    D->>RV: render_metrics_table(metrics)
    D->>RV: render_equity_curve(report)
    D->>RV: render_top_trades(report)
    RV-->>U: KPIs + Plotly-Figure + Trade-Tabelle

    alt Fehlerfall (Cache fehlt / unbekannte Strategie)
        DR->>RP: mark_error('deutsche Fehlermeldung')
        RP-->>U: st.error(...) im selben Tab
    end
```
