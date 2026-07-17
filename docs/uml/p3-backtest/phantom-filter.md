# UML: Slice 3.8 - Phantom-Ticker-Filter in der Suche

Status:    APPROVED
Phase:     P3 Backtest-Engine + Reports
Slice:     3.8 Phantom-Ticker-Filter in der Suche
Story:     US-P3.12 Phantom-Ticker aus Suche ausblenden

Mapped Requirements:
- NFR-Data-1: Cache-Pfad und Fallback-Kette unveraendert
- NFR-Sec-1: FMP-API-Key ausschliesslich aus `.env`
- NFR-Obs-1: Strukturiertes Logging entfernter Phantom-Treffer
- NFR-Ux-1: Bestehende deutsche UI-Texte und Fehlermeldungen

Der Filter wirkt ausschliesslich auf die Suchergebnisliste in
`_render_instrument_search`. DashboardRunner, BacktestOrchestrator,
ParquetCache und die Provider-Chain bleiben unveraendert.

## Structure

```mermaid
classDiagram
    class BacktestDashboard {
        +render_run_form() None
        -render_instrument_search() None
        -build_services() tuple
    }
    class CompanySearchService {
        -provider: InstrumentSearchProvider
        -phantom_validator: PhantomValidator
        +search(query: str, limit: int) list~Instrument~
    }
    class InstrumentSearchProvider {
        <<interface>>
        +search(query: str, limit: int) list~Instrument~
    }
    class FinancialModellingPrepProvider {
        +search(query: str, limit: int) list~Instrument~
    }
    class PhantomValidator {
        <<interface>>
        +is_real(symbol: str) bool
    }
    class FmpProfilePhantomValidator {
        -session: requests.Session
        -api_key: str
        +is_real(symbol: str) bool
    }
    class Instrument {
        +ticker: str
        +name: str
        +exchange: str
        +currency: str
    }
    class SearchUnavailableError {
        <<exception>>
    }

    BacktestDashboard --> CompanySearchService
    BacktestDashboard ..> FinancialModellingPrepProvider
    BacktestDashboard ..> FmpProfilePhantomValidator
    CompanySearchService --> InstrumentSearchProvider
    CompanySearchService --> PhantomValidator
    CompanySearchService --> Instrument
    FinancialModellingPrepProvider ..|> InstrumentSearchProvider
    FmpProfilePhantomValidator ..|> PhantomValidator
    CompanySearchService ..> SearchUnavailableError
```

## Flow

```mermaid
flowchart TD
    A([Trader klickt Unternehmen suchen]) --> B[CompanySearchService.search]
    B --> C[FMP Suche ausfuehren]
    C --> D{Treffer vorhanden?}
    D -->|Nein| E[Leere Liste zurueckgeben]
    D -->|Ja| F[PhantomValidator fuer jeden Treffer]
    F --> G{Validator verfuegbar?}
    G -->|Nein| H[Alle Treffer ungefiltert zurueckgeben]
    G -->|Ja| I{is_real symbol?}
    I -->|Nein Phantom| J[Treffer verwerfen log phantom_filtered]
    I -->|Ja real| K[Treffer behalten]
    J --> L{Gefilterte Liste leer?}
    K --> L
    L -->|Nein| M[Gefilterte Treffer zurueckgeben]
    L -->|Ja| N[Leere Liste zurueckgeben]
    M --> O[Dashboard zeigt Trefferliste]
    H --> O
    N --> P[Dashboard zeigt Keine Treffer]
    E --> P
```

## Sequence

```mermaid
sequenceDiagram
    actor T as Trader
    participant D as Dashboard
    participant S as CompanySearchService
    participant P as InstrumentSearchProvider
    participant V as PhantomValidator
    participant F as FMP Search
    participant PR as FMP Profile

    T->>D: Klickt Unternehmen suchen mit "apple"
    D->>S: search("apple")
    S->>P: search("apple")
    P->>F: GET /stable/search-name?query=apple
    F-->>P: list[Instrument] (inkl. AAPL.DE Phantom + APC.DE real)
    P-->>S: list[Instrument]
    S->>V: is_real("AAPL.DE")
    V->>PR: GET /stable/profile?symbol=AAPL.DE
    PR-->>V: {price: null, volume: 0}
    V-->>S: False (Phantom)
    S->>V: is_real("APC.DE")
    V->>PR: GET /stable/profile?symbol=APC.DE
    PR-->>V: {price: 291.65, volume: 49810}
    V-->>S: True (real)
    S-->>D: list[Instrument] ohne AAPL.DE
    D-->>T: Anzeige APC.DE und weitere reale Treffer

    alt Validator wirft Exception
        V-->>S: ProviderError
        S->>S: log phantom_validator_error
        S-->>D: list[Instrument] ungefiltert
        D-->>T: Trefferliste inkl. moeglicher Phantoms
    end
```
