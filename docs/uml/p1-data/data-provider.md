# UML: Slice 1.2 - DataProvider + Cache

Status:    DRAFT
Phase:     P1 Datenlayer
Slice:     1.2 DataProvider + Cache
Approved:  -

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
        -provider: FallbackProvider
        +get(ticker, start, end, granularity) Bars
        +summary() FetchSummary
    }
    class ParquetCache {
        -base_dir: Path
        +read(ticker, granularity, range) Bars
        +write(ticker, granularity, bars) Path
        +covers(ticker, granularity, range) bool
    }
    class FallbackProvider {
        -primary: DataProvider
        -secondary: DataProvider
        +fetch(ticker, start, end) Bars
    }
    class DataProvider {
        <<interface>>
        +fetch(ticker, start, end) Bars
    }
    class AlphaVantageProvider {
        -api_key: str
        -session: Session
        +fetch(ticker, start, end) Bars
    }
    class YFinanceProvider {
        +fetch(ticker, start, end) Bars
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
    DataService --> FallbackProvider
    FallbackProvider --> AlphaVantageProvider
    FallbackProvider --> YFinanceProvider
    DataProvider <|.. AlphaVantageProvider
    DataProvider <|.. YFinanceProvider
    FallbackProvider ..> DataProvider
    DataService ..> FetchSummary
```

## Flow

```mermaid
flowchart TD
    A([User: fetch_data.py --universe sp500 --granularity daily --years 5]) --> B[CLI parse args]
    B --> C[Load tickers from universe]
    C --> D[For each ticker]
    D --> E{ParquetCache.covers range?}
    E -->|yes| F[Log: cache.hit, ticker]
    F --> G[counter ok++]
    E -->|no| H[FallbackProvider.fetch ticker]
    H --> I{primary ok?}
    I -->|yes| J[Data available]
    I -->|no| K[Log: provider.fallback reason]
    K --> L{secondary ok?}
    L -->|yes| J
    L -->|no| M{primary says ticker not found?}
    M -->|yes| N[Fail fast: ticker.not_found]
    N --> Z1([Exit 1, no partial cache write])
    M -->|no| O[Log: data.unavailable]
    O --> Z2([Continue other tickers, counter failed++])
    J --> P[ParquetCache.write ticker]
    P --> Q[counter ok++]
    G --> R{more tickers?}
    Q --> R
    R -->|yes| D
    R -->|no| S[Log summary: ok, fallback, failed, duration]
    S --> T([Exit 0])
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant CLI as FetchDataCLI
    participant DS as DataService
    participant C as ParquetCache
    participant FP as FallbackProvider
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
            DS->>FP: fetch(ticker, start, end)
            FP->>AV: fetch(ticker, start, end)
            alt AV success
                AV-->>FP: Bars
            else AV error
                AV-->>FP: raise ProviderError
                FP->>Log: provider.fallback(reason=alpha_vantage.rate_limited)
                FP->>YF: fetch(ticker, start, end)
                alt YF success
                    YF-->>FP: Bars
                else YF error
                    YF-->>FP: raise ProviderError
                    alt error indicates unknown ticker
                        FP-->>DS: raise TickerNotFound
                        DS-->>CLI: raise TickerNotFound
                        CLI-->>U: stderr: ticker.not_found: ZZZZZ, exit 1
                    else other error
                        FP-->>DS: raise DataUnavailable
                        DS->>Log: data.unavailable(ticker, reason)
                        DS-->>CLI: continue (counter failed++)
                    end
                end
            end
            FP-->>DS: Bars
            DS->>C: write(ticker, daily, bars)
            C-->>DS: path
        end
        DS-->>CLI: Bars
    end
    CLI->>Log: fetch.summary(ok=N, fallback=N, failed=N, duration_s=...)
    CLI-->>U: exit 0
```