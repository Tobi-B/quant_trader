# UML: Slice 2.6 - Strategy Documentation Viewer

Status:    APPROVED
Phase:     P2 Strategien (Erweiterung)
Slice:     2.6 Strategy Documentation Viewer
Approved:  2026-07-15

Mapped Requirements:
- NFR-Ux-1: Deutsche UI-Texte + deutsche README-Inhalte
- NFR-Obs-1: Strukturiertes Logging (dashboard.strategies.rendered)

Stories:
- US-P2.8: Strategie-Doku im Dashboard abrufbar

Erweitert die registrierten Strategien um Markdown-READMEs und das
Streamlit-Dashboard um einen "Strategien"-Tab. Bestehende Klassen
`StrategyLoader`, `StrategyBase`, `SmaCrossStrategy` etc. werden
NICHT geaendert.

## Structure

```mermaid
classDiagram
    class StrategyDocLoader {
        -_dir: Path
        +load(strategy_name) str | None
        +list_documented() list~str~
    }
    class Settings {
        +strategy_docs_dir: Path = Path("./docs/strategies")
    }
    class StrategyLoader {
        +registered_names() list~str~
    }
    class ReadmeFile {
        <<file: docs/strategies/*.md>>
        +name: str
        +content: str
    }
    class StreamlitTab {
        <<UI: Strategien-Tab>>
        +strategies: list~str~
        +selected: str | None
        +expander(name, version, doc, params) None
    }
    class BacktestDashboard {
        +tabs: RunForm / ReadMode / Vergleich / Cache / Strategien
    }

    StrategyDocLoader --> ReadmeFile
    StrategyDocLoader --> Settings
    StreamlitTab --> StrategyDocLoader
    StreamlitTab --> StrategyLoader
    BacktestDashboard --> StreamlitTab
```

## Flow

```mermaid
flowchart TD
    A([User: oeffnet Streamlit Dashboard, klickt Tab 'Strategien']) --> B[StrategienTab.render]
    B --> C[loader = StrategyDocLoader settings.strategy_docs_dir]
    B --> D[registered = StrategyLoader.default_loader.registered_names]
    D --> E[Pro Strategie: st.expander name, vversion]
    E --> F{doc = loader.load name vorhanden?}
    F -->|yes| G[st.markdown doc]
    F -->|no| H[st.warning Keine Doku: docs/strategies/name.md]
    G --> I[st.dataframe default_params.items]
    H --> I
    I --> J[naechste Strategie]
    J --> K{Alle Strategien?}
    K -->|no| E
    K -->|yes| L[log dashboard.strategies.rendered mit Anzahl]
    L --> M([User sieht Strategien mit/ohne Doku])
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant D as BacktestDashboard (Strategien Tab)
    participant L as StrategyLoader
    participant DL as StrategyDocLoader
    participant F as ReadmeFile (docs/strategies/X.md)
    participant Log as structlog

    U->>D: klickt Tab 'Strategien'
    D->>L: registered_names()
    L-->>D: [sma_cross, momentum, rsi_mean_reversion, etf_rotation]
    D->>DL: StrategyDocLoader(settings.strategy_docs_dir)

    loop pro Strategie
        D->>DL: load(sma_cross)
        DL->>F: read docs/strategies/sma_cross.md
        F-->>DL: "# SMA-Cross\n\n## Was?\n..."
        DL-->>D: markdown_content
        D->>D: st.expander("sma_cross (v1.0.0)")
        D->>D: st.markdown(markdown_content)
        D->>D: st.dataframe(default_params.items)
    end

    D->>Log: dashboard.strategies.rendered count=4 documented=4
```

## Notes

- README-Files unter `docs/strategies/` (Convention: filename =
  `StrategyLoader.registered_names()`-Eintrag)
- Markdown mit Sections: Was?, Wann BUY/SELL?, Parameter, Risiken,
  Beispiel
- Deutsche Texte (NFR-Ux-1)
- Loader hat einfache Fallback-Logik: fehlende Datei -> None ->
  `st.warning` im Dashboard
- Default-Params aus `StrategyLoader._registry[name].default_params`
- Backward-Compat: keine Aenderung an Strategie-Klassen, 479 Tests
  unveraendert gruen
