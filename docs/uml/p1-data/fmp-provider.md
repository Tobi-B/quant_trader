# UML: Slice 1.5 - Financial Modelling Prep (FMP) Provider

Status:    APPROVED
Phase:     P1 Datenlayer
Slice:     1.5 FMP-Provider
Approved:  2026-07-14

Mapped Requirements:
- NFR-Data-3: FMP als Primary Provider (Free-Tier 250 calls/Tag) - DRAFT -> APPROVED
- NFR-Sec-1: API-Key via .env, niemals im Repo
- NFR-Rel-1: Daten-Fetch idempotent (via DataService-Cache)
- NFR-Perf-2: Daten-Fetch fuer ein Ticker 5 Jahre < 60s

Stories:
- keine neue User-Story (NFR-getriebener Provider-Slice, dokumentiert in ADR-0009)

Erweitert die bestehende Provider-Chain (ADR-0001) um FMP als neuen
Primary. Bestehende Klassen `DataProvider` Protocol, `FallbackProvider`,
`DataService` und `ParquetCache` werden wiederverwendet.

## Structure

```mermaid
classDiagram
    class DataProvider {
        <<interface>>
        +fetch(ticker, start, end, granularity) list~Bar~
        +name str
    }
    class FinancialModellingPrepProvider {
        +name = "fmp"
        +api_key: str
        -_session: Session
        -_base_url: str
        -_endpoint_map: dict~Granularity, str~
        +fetch(ticker, start, end, granularity) list~Bar~
        -_parse_response(payload, granularity, start, end) list~Bar~
    }
    class AlphaVantageProvider {
        +name = "alphavantage"
    }
    class YFinanceProvider {
        +name = "yfinance"
    }
    class StockDataProvider {
        +name = "stockdata"
    }
    class FallbackProvider {
        -_primary: object
        -_fallbacks: list~object~
        -_chain: list~object~
        +fetch(ticker, start, end, granularity) list~Bar~
    }
    class Settings {
        +fmp_api_key: str
        +alphavantage_key: str
        +stockdata_api_token: str
    }
    class DataService {
        -_cache: ParquetCache
        -_provider: object
        +get(ticker, start, end, granularity) FetchResult
    }

    DataProvider <|.. FinancialModellingPrepProvider
    DataProvider <|.. AlphaVantageProvider
    DataProvider <|.. YFinanceProvider
    DataProvider <|.. StockDataProvider
    FallbackProvider --> FinancialModellingPrepProvider : primary
    FallbackProvider --> YFinanceProvider : fallback 1
    FallbackProvider --> StockDataProvider : fallback 2
    FallbackProvider --> AlphaVantageProvider : fallback 3
    DataService --> FallbackProvider
    Settings --> FinancialModellingPrepProvider
```

## Flow

```mermaid
flowchart TD
    A([DataService.get ticker, start, end, granularity]) --> B{Cache covers?}
    B -->|yes| C[read from ParquetCache]
    C --> Z([return cached bars])
    B -->|no| D[FallbackProvider.fetch]
    D --> E[provider 0: FMP]
    E --> F{fetch ok?}
    F -->|yes| G[parses Response, bars, write cache]
    G --> Z
    F -->|RateLimitedError| H[log provider.fallback reason]
    H --> I[provider 1: YFinance]
    F -->|ProviderError| I
    F -->|TickerNotFoundError| X([raise, fail-fast])
    I --> J{fetch ok?}
    J -->|yes| G
    J -->|no| K[provider 2: StockData]
    K --> L{fetch ok?}
    L -->|yes| G
    L -->|no| M[provider 3: AlphaVantage]
    M --> N{fetch ok?}
    N -->|yes| G
    N -->|no| O[raise DataUnavailableError]
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant DS as DataService
    participant FP as FallbackProvider
    participant FMP as FinancialModellingPrepProvider
    participant YF as YFinanceProvider
    participant SD as StockDataProvider
    participant AV as AlphaVantageProvider
    participant Cache as ParquetCache
    participant API as FMP-API

    U->>DS: get(SPY, 2020-01-01, 2024-12-31, DAILY)
    DS->>Cache: covers?
    Cache-->>DS: false
    DS->>FP: fetch(SPY, 2020-01-01, 2024-12-31, DAILY)
    FP->>FMP: fetch(SPY, 2020-01-01, 2024-12-31, DAILY)
    FMP->>API: GET /historical-price-full/SPY?from=2020-01-01&to=2024-12-31&apikey=XXX
    API-->>FMP: 200 {"symbol": "SPY", "historical": [...]}
    FMP->>FMP: parse_response (camelCase -> snake_case, date filter, sort)
    FMP-->>FP: list[Bar]
    FP-->>DS: list[Bar]
    DS->>Cache: write(SPY, DAILY, bars)
    DS-->>U: FetchResult(ticker, bars, from_cache=False, used_provider=fmp)

    alt FMP RateLimitedError (Free-Tier 250/Tag)
        FMP-->>FP: RateLimitedError("Limit Reach")
        FP->>YF: fetch(...)
        YF-->>FP: list[Bar]
        FP-->>DS: list[Bar]
    end

    alt FMP network error
        FMP-->>FP: ProviderError("network: ...")
        FP->>YF: fetch(...)
        YF-->>FP: ProviderError
        FP->>SD: fetch(...)
        SD-->>FP: ProviderError
        FP->>AV: fetch(...)
        AV-->>FP: ProviderError
        FP-->>DS: raise DataUnavailableError(SPY, reasons)
    end
```

## Notes

- `FinancialModellingPrepProvider` wirft `RateLimitedError` bei
  `Limit Reach` (HTTP 200 mit `Error Message`); `FallbackProvider`
  schaltet automatisch weiter.
- `TickerNotFoundError` schlaegt sofort durch (fail-fast) - gilt fuer
  alle Provider in der Kette.
- `FinancialModellingPrepProvider.fetch` liest `settings.fmp_api_key`
  via Dependency Injection im Factory (`build_chain(settings)`).
- Wenn `fmp_api_key` leer: Provider wird erzeugt, wirft aber bei
  erstem Fetch `ProviderError("FINANCIAL_MODELLING_PREP_KEY not set")`,
  was den Fallback triggert.
