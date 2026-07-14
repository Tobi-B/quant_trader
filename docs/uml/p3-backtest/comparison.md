# UML: Slice 3.6 - Dashboard Strategie-Vergleichsansicht

Status:    APPROVED
Phase:     P3 Backtest
Slice:     3.6 Strategie-Vergleichsansicht
Approved:  2026-07-14

Mapped Requirements:
- NFR-Ux-1: Deutsche UI-Texte im Vergleichs-Tab

Stories:
- US-P3.10: Registrierte Strategien im Dashboard vergleichen

Erweitert das Streamlit-Dashboard (Slices 3.3 + 3.5) um einen dritten
Tab "Vergleich". Bestehende Klassen `BacktestDashboard`, `RunForm`,
`DashboardRunner`, `ReportLoader` werden wiederverwendet; neu ist die
`StrategySelector`-Logik und die `ComparisonView`-Komponente.

## Structure

```mermaid
classDiagram
    class BacktestDashboard {
        +render() None
    }
    class ComparisonView {
        +render(loader, strategy_names) None
    }
    class StrategySelector {
        +latest_runs_by_strategy(loader, strategy_names) dict~str, RunSummary|None~
    }
    class ComparisonTable {
        +build_rows(summaries) list~ComparisonRow~
        +sort_by_sharpe_desc(rows) list~ComparisonRow~
    }
    class ComparisonRow {
        +strategy_name: str
        +version: str
        +latest_run_id: str | None
        +total_return_pct: float | None
        +sharpe: float | None
        +max_drawdown_pct: float | None
        +cagr_pct: float | None
        +n_trades: int | None
        +exposure_pct: float | None
    }
    class EquityMiniChart {
        +render(loader, run_id, strategy_name) None
    }
    class ReportLoader {
        +list_runs() list~RunSummary~
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

    BacktestDashboard --> ComparisonView
    ComparisonView --> StrategySelector
    ComparisonView --> ComparisonTable
    ComparisonView --> EquityMiniChart
    StrategySelector --> ReportLoader
    StrategySelector --> RunSummary
    ComparisonTable --> ComparisonRow
    EquityMiniChart --> ReportLoader
```

## Flow

```mermaid
flowchart TD
    A([User: streamlit run scripts/backtest_dashboard.py]) --> B[BacktestDashboard.render]
    B --> C{st.tabs Run-Form / Read-Mode / Vergleich}
    C --> D[Tab 'Vergleich' aktiv]
    D --> E[StrategySelector.latest_runs_by_strategy loader, registered_names]
    E --> F[ReportLoader.list_runs reports/]
    F --> G[Gruppieren nach strategy_name, je neuester start]
    G --> H{dict: name -> RunSummary | None}
    H --> I{Strategien registriert?}
    I -->|no| J[st.info Keine Strategien registriert]
    I -->|yes| K[ComparisonTable.build_rows summaries]
    K --> L[ComparisonTable.sort_by_sharpe_desc rows]
    L --> M[st.dataframe mit Spalten Strategie/Version/letzter Run/Metriken]
    M --> N{Reports vorhanden?}
    N -->|no| O[st.info Noch keine Backtests gelaufen]
    N -->|yes| P[EquityMiniChart.render pro Strategie in st.columns 2]
    P --> Q[Pro Zeile Button Backtest starten -> st.session_state active_tab=Run-Form, selected_strategy]
    Q --> R([User kann in Run-Form-Tab wechseln mit vorausgewaehlter Strategie])
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant D as BacktestDashboard
    participant V as ComparisonView
    participant S as StrategySelector
    participant L as ReportLoader
    participant T as ComparisonTable
    participant E as EquityMiniChart
    participant SS as st.session_state

    U->>D: oeffnet Browser, klickt Tab 'Vergleich'
    D->>V: render(loader, strategy_names)
    V->>S: latest_runs_by_strategy(loader, strategy_names)
    S->>L: list_runs()
    L-->>S: list[RunSummary]
    S-->>V: dict[strategy_name -> RunSummary | None]
    V->>T: build_rows(summaries)
    T-->>V: list[ComparisonRow]
    V->>T: sort_by_sharpe_desc(rows)
    T-->>V: sorted list[ComparisonRow]
    V-->>D: st.dataframe + Equity-Charts

    alt Reports vorhanden
        loop pro Strategie mit Run
            V->>E: render(loader, run_id, strategy_name)
            E->>L: load_run(run_id)
            L-->>E: BacktestReport
            E-->>V: Plotly-Mini-Chart
        end
    end

    U->>V: klickt 'Backtest starten' fuer Strategie X
    V->>SS: set active_tab='Run-Form', selected_strategy='X'
    V-->>D: st.rerun
    D->>D: Run-Form-Tab liest selected_strategy, pre-fillt Selectbox
```
