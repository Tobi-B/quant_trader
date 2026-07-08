# UML: Slice 1.2 - DataProvider + Cache

Status:    APPROVED
Phase:     P1 Datenlayer
Slice:     1.2 DataProvider + Cache
Approved:  2026-07-08

Mapped Requirements:
- NFR-Rel-1: Daten-Fetch idempotent
- NFR-Perf-2: Daten-Fetch fuer ein Ticker 5 Jahre < 60 s
- NFR-Data-1: Parquet-Cache mit Inkrement-Update (Out-of-Scope hier: kein Auto-Refresh)
- NFR-Obs-1: Strukturiertes Logging (JSON)
- NFR-Ux-1: CLI-Texte deutsch, klare Fehlermeldungen

Stories:
- US-P1.2: Historische Tagessdaten fuer eine Liste laden
- US-P1.3: Cache schlaegt zu, kein Reload
- US-P1.4: Automatischer Fallback bei Provider-Fehler
- US-P1.6: Klare Fehlermeldung bei ungueltigem Ticker

## Structure

```mermaid
classDiagram
    class DataService {
        -cache: ParquetCache
        -provider: DataProvider
        +get(ticker, start, end, granularity) Bars
        +summary() FetchSummary
    }
    class ParquetCache {
        -base_dir: Path
        +read(ticker, granularity, range) Bars
        +write(ticker, granularity, bars) Path
        +covers(ticker, granularity, range) bool
    }
    class DataProvider {
        <<interface>>
        +fetch(ticker, start, end, granularity) Bars
    }
    class FallbackProvider {
        -_primary: DataProvider
        -_fallbacks: list~DataProvider~
        +__init__(primary, fallbacks)
        +fetch(ticker, start, end, granularity) Bars
    }
    class AlphaVantageProvider {
        -_api_key: str
        -_session: Session
        +fetch(ticker, start, end, granularity) Bars
    }
    class YFinanceProvider {
        +fetch(ticker, start, end, granularity) Bars
    }
    class ProviderFactory {
        <<module>>
        +build_chain(settings) DataProvider
    }
    class FetchDataCLI {
        +main(args) int
    }
    class FetchSummary {
        +ok: int
        +fallback: int
        +failed: int
        +duration_s: float
    }

    FetchDataCLI --> DataService
    DataService --> ParquetCache
    DataService --> DataProvider
    FallbackProvider o-- DataProvider : wraps
    DataProvider <|.. FallbackProvider : implements
    DataProvider <|.. AlphaVantageProvider : implements
    DataProvider <|.. YFinanceProvider : implements
    ProviderFactory ..> FallbackProvider : builds
    ProviderFactory ..> AlphaVantageProvider : instantiates
    ProviderFactory ..> YFinanceProvider : instantiates
    DataService ..> FetchSummary
```

Hinweis zur Beziehung: `FallbackProvider o-- DataProvider` ist Aggregation
(offene Raute). Der Decorator haelt eine Referenz auf einen DataProvider,
besitzt ihn aber nicht. Eine zweite Aggregation an die Liste ist ueber die
Multiplizitaet `fallbacks: list~DataProvider~` ausgedrueckt.

## Provider-Setup

```mermaid
sequenceDiagram
    participant App as App startup
    participant S as Settings
    participant F as ProviderFactory
    participant AV as AlphaVantageProvider
    participant YF as YFinanceProvider
    participant Dec as FallbackProvider
    participant C as ParquetCache
    participant DS as DataService

    App->>S: load(env)
    S-->>App: Settings(alphavantage_key, data_dir)
    App->>F: build_chain(settings)
    F->>AV: __init__(api_key=settings.alphavantage_key)
    F->>YF: __init__()
    F->>Dec: __init__(primary=AV, fallbacks=[YF])
    Dec-->>F: ready
    F-->>App: DataProvider (FallbackProvider instance)
    App->>C: __init__(base_dir=settings.data_dir)
    App->>DS: __init__(cache=C, provider=Dec)
    App-->>App: DataService ready
```

Der Factory (`quant_trader.data.factory`) ist die einzige Stelle, an der die
Provider-Instanzen erzeugt werden. Hinzufuegen eines weiteren Anbieters
(z.B. Polygon spaeter) erfordert nur eine Aenderung in `ProviderFactory`,
nicht in `DataService` oder `FallbackProvider`.

## Flow

```mermaid
flowchart TD
    A([User: fetch_data.py --universe sp500 --granularity daily --years 5]) --> B[CLI parse args]
    B --> C[Load tickers from universe]
    C --> D[For each ticker]
    D --> E{ParquetCache.covers range?}
    E -->|yes| F[Log: cache.hit]
    F --> G[counter ok++]
    E -->|no| H[FallbackProvider.fetch ticker]
    H --> I[Loop: for provider in primary + fallbacks]
    I --> J{provider ok?}
    J -->|yes| K[Bars]
    J -->|no| L[log provider.fallback reason]
    L --> M{next provider?}
    M -->|yes| I
    M -->|no| N{last error = TickerNotFound?}
    N -->|yes| O[Fail fast: ticker.not_found]
    O --> Z1([Exit 1, no partial cache write])
    N -->|no| P[Log: data.unavailable]
    P --> Z2([Continue other tickers, counter failed++])
    K --> Q[ParquetCache.write ticker]
    Q --> R[counter ok++]
    G --> S{more tickers?}
    R --> S
    S -->|yes| D
    S -->|no| T[Log summary: ok, fallback, failed, duration]
    T --> U([Exit 0])
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant CLI as FetchDataCLI
    participant DS as DataService
    participant C as ParquetCache
    participant Dec as FallbackProvider
    participant AV as AlphaVantageProvider
    participant YF as YFinanceProvider
    participant Log as structlog

    U->>CLI: --universe sp500 --granularity daily --years 5
    loop for each ticker in universe
        CLI->>DS: get(ticker, range, daily)
        DS->>C: covers(ticker, daily, range)?
        alt cache hit
            C-->>DS: True
            DS->>C: read(ticker, daily, range)
            C-->>DS: Bars
            DS->>Log: cache.hit(ticker)
        else cache miss
            C-->>DS: False
            DS->>Dec: fetch(ticker, start, end, daily)
            loop for provider in primary + fallbacks
                Dec->>provider: fetch(ticker, start, end, daily)
                alt provider success
                    provider-->>Dec: Bars
                    Dec-->>DS: Bars (break loop)
                else provider raises ProviderError
                    provider-->>Dec: raise
                    Dec->>Log: provider.fallback(provider=name, reason=...)
                end
            end
            alt TickerNotFound
                Dec-->>DS: raise TickerNotFound
                DS-->>CLI: raise TickerNotFound
                CLI-->>U: stderr: ticker.not_found: ZZZZZ, exit 1
            else DataUnavailable
                Dec-->>DS: raise DataUnavailable
                DS->>Log: data.unavailable(ticker, reason)
                DS-->>CLI: continue (counter failed++)
            else Bars received
                DS->>C: write(ticker, daily, bars)
                C-->>DS: path
                DS-->>CLI: Bars
            end
        end
    end
    CLI->>Log: fetch.summary(ok=N, fallback=N, failed=N, duration_s=...)
    CLI-->>U: exit 0
```