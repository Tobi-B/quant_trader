# UML: Slice 1.3 - Intraday-Support

Status:    DRAFT
Phase:     P1 Datenlayer
Slice:     1.3 Intraday
Approved:  -

Mapped Requirements:
- NFR-Perf-2: Daten-Fetch-Performance-Budget (Intraday warnt)
- NFR-Data-1: Parquet-Cache granuliert nach Granularitaet

Stories:
- US-P1.5: Intraday-Daten (Stunden oder Minuten) optional laden

Hinweis: Slice 1.3 erweitert Slice 1.2 nur um die Granularitaetsdimension. Structure/Components sind identisch, Flow/Sequence zeigen nur den Granularitaetszweig.

## Structure

```mermaid
classDiagram
    class Granularity {
        <<enum>>
        DAILY
        INTRADAY_60M
        INTRADAY_15M
        +path_segment() str
    }
    class ParquetCache {
        -base_dir: Path
        +read(ticker, granularity, range) Bars
        +write(ticker, granularity, bars) Path
        +covers(ticker, granularity, range) bool
    }
    class DataService {
        +get(ticker, start, end, granularity) Bars
    }
    class DataProvider {
        <<interface>>
        +fetch(ticker, start, end, granularity) Bars
    }
    class AlphaVantageProvider {
        +fetch(ticker, start, end, granularity) Bars
    }
    class YFinanceProvider {
        +fetch(ticker, start, end, granularity) Bars
    }

    ParquetCache ..> Granularity
    DataService --> Granularity
    DataProvider <|.. AlphaVantageProvider
    DataProvider <|.. YFinanceProvider
    DataService --> DataProvider
```

## Flow

```mermaid
flowchart TD
    A([User: fetch_data.py AAPL --granularity 60m --years 1]) --> B[CLI parse args]
    B --> C{Granularity?}
    C -->|daily| D[path: data/raw/daily/AAPL.parquet]
    C -->|intraday| E[Log warnung: intraday.api_quota_high]
    E --> F[path: data/raw/60m/AAPL.parquet]
    D --> G[DataService.get ticker daily]
    F --> H[DataService.get ticker 60m]
    G --> I{Cache covers?}
    H --> I
    I -->|yes| J[Log: cache.hit]
    I -->|no| K[FallbackProvider.fetch ticker, granularity]
    K --> L[ParquetCache.write ticker, granularity]
    L --> M[Log: fetch.summary]
    J --> M
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant CLI as FetchDataCLI
    participant DS as DataService
    participant C as ParquetCache
    participant FP as FallbackProvider
    participant Log as structlog

    U->>CLI: AAPL --granularity 60m --years 1
    CLI->>CLI: parse granularity=INTRADAY_60M
    CLI->>Log: warn(intraday.api_quota_high)
    CLI->>DS: get(AAPL, 1y, INTRADAY_60M)
    DS->>C: covers(AAPL, 60m, range)?
    alt cache hit
        C-->>DS: True
        DS->>C: read(AAPL, 60m, range)
        C-->>DS: Bars
        DS->>Log: cache.hit(AAPL, 60m)
    else cache miss
        C-->>DS: False
        DS->>FP: fetch(AAPL, range, 60m)
        FP-->>DS: Bars
        DS->>C: write(AAPL, 60m, bars)
        C-->>DS: path
    end
    DS-->>CLI: Bars
    CLI-->>U: exit 0
```