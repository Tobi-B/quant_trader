# UML: Slice 3.3 - Report (Console + Plotly + JSON + Streamlit)

Status:    APPROVED
Phase:     P3 Backtest
Slice:     3.3 Report
Approved:  2026-07-14

Mapped Requirements:
- NFR-Ux-1: CLI-Texte deutsch, klar
- NFR-Data-2: Adj. Close fuer Equity

Stories:
- US-P3.4: Backtest-Ergebnisse als Console-Tabelle
- US-P3.5: Equity-Curve als interaktives Plotly-HTML
- US-P3.6: Backtest als JSON exportieren
- US-P3.7: Streamlit-Dashboard fuer Backtest-Vergleich

## Structure

```mermaid
classDiagram
    class ReportBuilder {
        +build(result: BacktestResult, output_dir: Path) ReportPaths
    }
    class ConsoleFormatter {
        +format_metrics(metrics) str
        +format_trades(trades, top=10) str
        +format_report(result) str
    }
    class PlotlyExporter {
        +export_equity_curve(result, path) Path
    }
    class JsonExporter {
        +export(result, path) Path
    }
    class ReportPaths {
        +console: str
        +equity_html: Path
        +result_json: Path
    }
    class BacktestReport {
        +run_id: str
        +strategy_name: str
        +params: dict
        +start: date
        +end: date
        +fill_mode: str
        +initial_cash: float
        +final_equity: float
        +metrics: Metrics
        +equity_curve: list~dict~
        +trades: list~dict~
    }

    ReportBuilder --> ConsoleFormatter
    ReportBuilder --> PlotlyExporter
    ReportBuilder --> JsonExporter
    ReportBuilder --> ReportPaths
    JsonExporter --> BacktestReport
```

## Streamlit-Dashboard (Sub-Slice)

```mermaid
classDiagram
    class BacktestDashboard {
        +render() None
    }
    class ReportLoader {
        +list_runs(reports_dir) list~RunSummary~
        +load_run(run_id) BacktestReport
    }
    class RunSummary {
        +run_id: str
        +strategy_name: str
        +start: date
        +end: date
        +final_equity: float
        +sharpe: float | None
    }
    class EquityPlot {
        +render_plotly(report) Figure
    }
    class DrawdownIndicator {
        +render_kpi(metrics) None
    }

    BacktestDashboard --> ReportLoader
    BacktestDashboard --> EquityPlot
    BacktestDashboard --> DrawdownIndicator
    ReportLoader --> RunSummary
    ReportLoader --> BacktestReport
```

## Flow

```mermaid
flowchart TD
    A([BacktestResult]) --> B[ReportBuilder.build]
    B --> C{--no-report?}
    C -->|yes| D[ConsoleFormatter only]
    C -->|no| E[mkdir reports/run-id/]
    E --> F[PlotlyExporter.export_equity_curve]
    F --> G[JsonExporter.export]
    G --> D
    D --> H[stdout: metrics + top-10 trades table]
    H --> I[return ReportPaths]
    I --> J([CLI: print paths + Exit 0])

    K([User: streamlit run scripts/backtest_dashboard.py]) --> L[ReportLoader.list_runs reports/]
    L --> M{Runs vorhanden?}
    M -->|no| N[zeige Hinweis: Noch keine Backtests]
    M -->|yes| O[Sidebar: Strategie-Selector, Run-Selector]
    O --> P[ReportLoader.load_run selected]
    P --> Q[EquityPlot.render_plotly]
    P --> R[DrawdownIndicator.render_kpi]
    P --> S[ConsoleFormatter.format_trades as dataframe]
    Q --> T([Main: Plotly-Figure + KPI + Trade-Tabelle])
    R --> T
    S --> T
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant CLI as BacktestCLI
    participant RB as ReportBuilder
    participant CF as ConsoleFormatter
    participant PE as PlotlyExporter
    participant JE as JsonExporter

    U->>CLI: run --strategy sma_cross --ticker SPY ...
    CLI->>RB: build(BacktestResult, reports/<run-id>/)
    RB->>PE: export_equity_curve(result, equity_curve.html)
    PE-->>RB: Path
    RB->>JE: export(result, result.json)
    JE-->>RB: Path
    RB->>CF: format_report(result)
    CF-->>RB: str
    RB-->>CLI: ReportPaths
    CLI->>U: print ConsoleFormatter output
    CLI-->>U: Exit 0 + log paths
```