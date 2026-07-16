# UML: Slice 3.7 - Unternehmens- und Ticker-Suche im Dashboard

Status:    DRAFT
Phase:     P3 Backtest-Engine + Reports
Slice:     3.7 Unternehmens- und Ticker-Suche im Dashboard
Story:     US-P3.11 Unternehmen ohne bekannten Ticker finden

Mapped Requirements:
- NFR-Ux-1: Deutsche UI-Texte und klare, actionable Fehlermeldungen
- NFR-Data-1: Die gewählte Instrument-Auswahl verwendet weiterhin den bestehenden Daten- und Cachepfad
- NFR-Sec-1: Zugangsdaten für die Suchdatenquelle kommen ausschließlich aus der Umgebung

Die Suche ergänzt ausschließlich den Custom-Ticker-Teil des bestehenden Run-Forms.
Universe-Presets bleiben unverändert. Ein ausgewähltes Suchergebnis liefert nur den
Ticker an den bestehenden `DashboardRunner`; Backtest-Orchestrator und Cachepfad
werden nicht verändert.

## Structure

```mermaid
classDiagram
    class BacktestDashboard {
        +render_run_form() None
        -render_instrument_search() None
    }
    class InstrumentSearchService {
        -provider: InstrumentSearchProvider
        +search(query: str) list~Instrument~
    }
    class InstrumentSearchProvider {
        <<interface>>
        +search(query: str) list~Instrument~
    }
    class MarketSearchProvider {
        +search(query: str) list~Instrument~
    }
    class Instrument {
        +ticker: str
        +name: str
        +exchange: str
        +currency: str
    }
    class DashboardRunner {
        +run_request(strategy_name, ticker, universe_preset, start, end) tuple
    }
    class BacktestOrchestrator {
        +run(...) BacktestResult
    }
    class ParquetCache {
        +read(ticker, granularity, start, end) list~Bar~
    }
    class SearchUnavailableError {
        <<exception>>
    }

    BacktestDashboard --> InstrumentSearchService
    BacktestDashboard --> DashboardRunner
    InstrumentSearchService --> InstrumentSearchProvider
    InstrumentSearchService --> Instrument
    MarketSearchProvider ..|> InstrumentSearchProvider
    InstrumentSearchProvider ..> SearchUnavailableError
    BacktestDashboard ..> SearchUnavailableError
    DashboardRunner --> BacktestOrchestrator
    BacktestOrchestrator --> ParquetCache
```

## Flow

```mermaid
flowchart TD
    A([Trader öffnet Run-Form]) --> B{Custom-Ticker ausgewählt?}
    B -->|Nein: Universe-Preset| C[Universe bleibt unverändert]
    B -->|Ja| D[Unternehmensname oder Ticker eingeben]
    D --> E{Suchanfrage gültig?}
    E -->|Nein| F[Hinweis: Suchbegriff eingeben]
    F --> D
    E -->|Ja| G[InstrumentSearchService sucht Treffer]
    G --> H{Suchdienst verfügbar?}
    H -->|Nein| I[Deutsche Fehlermeldung anzeigen]
    I --> J[Freien Ticker weiter manuell eingeben]
    H -->|Ja| K{Treffer vorhanden?}
    K -->|Nein| L[Hinweis: Keine Treffer]
    L --> D
    K -->|Ja| M[Name, Ticker und Börsenplatz anzeigen]
    M --> N{Trader wählt Instrument?}
    N -->|Nein| D
    N -->|Ja| O[Ticker ins Backtest-Formular übernehmen]
    C --> P[Backtest starten]
    O --> P
    J --> P
    P --> Q[DashboardRunner.run_request]
    Q --> R[Bestehender Orchestrator- und Cachepfad]
    R --> S([Backtest-Ergebnis anzeigen])
```

## Sequence

```mermaid
sequenceDiagram
    actor T as Trader
    participant D as Dashboard
    participant S as InstrumentSearchService
    participant P as InstrumentSearchProvider
    participant M as Marktdaten-Suchdienst
    participant R as DashboardRunner
    participant O as BacktestOrchestrator
    participant C as ParquetCache

    T->>D: Wählt Custom-Ticker und gibt "Apple" ein
    D->>S: search("Apple")
    S->>P: search("Apple")
    P->>M: Suchanfrage mit Suchbegriff
    M-->>P: Treffer mit Name, Ticker, Börsenplatz
    P-->>S: list[Instrument]
    S-->>D: Trefferliste
    D-->>T: Anzeige der Instrumente
    T->>D: Wählt Apple Inc. / AAPL / NASDAQ
    D-->>T: Ticker AAPL im Formular übernommen
    T->>D: Klickt "Backtest starten"
    D->>R: run_request(..., ticker="AAPL", universe_preset=None)
    R->>O: run(..., ticker="AAPL")
    O->>C: read("AAPL", Zeitraum)
    C-->>O: Historische Bars
    O-->>R: BacktestResult
    R-->>D: Ergebnis
    D-->>T: Metriken, Equity-Curve und Trades

    alt Keine Treffer
        M-->>P: Leere Trefferliste
        P-->>S: []
        S-->>D: Keine Treffer
        D-->>T: Deutsche Meldung und Möglichkeit zur neuen Suche
    else Suchdienst nicht verfügbar
        M-->>P: Provider-Fehler
        P-->>S: SearchUnavailableError
        S-->>D: Fehlermeldung
        D-->>T: Formular bleibt für manuelle Eingabe nutzbar
    end
```
