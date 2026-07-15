# UML: Slice 1.6 - Cache Refresh (Bulk + Inkrementell + UI)

Status:    APPROVED
Phase:     P1 Datenlayer (Erweiterung)
Slice:     1.6 Cache Refresh
Approved:  2026-07-15

Mapped Requirements:
- NFR-Data-1: Inkrement-Update (kein Full-Refetch bei Overlap) - jetzt vollstaendig
- NFR-Perf-2: <60s fuer 5y Cache-Miss (pro Ticker)
- NFR-Ux-1: Deutsche UI-Texte im Dashboard
- NFR-Obs-1: Strukturiertes Logging (data.refresh.*, cache.merge_incremental)

Stories:
- US-P1.8: Inkrement-Update: nur fehlende Bars nachladen
- US-P1.9: Cache-Refresh-Button im Streamlit Dashboard

Erweitert Slice 1.2 (Parquet-Cache) und Slice 3.5 (Dashboard) um
einen Refresh-Mechanismus. Bestehende Provider-Chain (FMP -> YFinance
-> StockData -> AlphaVantage) aus ADR-0009 wird wiederverwendet.

## Structure

```mermaid
classDiagram
    class ParquetCache {
        -_base: Path
        +read(ticker, granularity, start, end) list~Bar~
        +write(ticker, granularity, bars) Path
        +covers(ticker, granularity, start, end) bool
        +covers_range(ticker, granularity, start, end) tuple
        +merge_incremental(ticker, granularity, new_bars) Path
        +list_cached_tickers(granularity) list~str~
    }
    class DataService {
        -_cache: ParquetCache
        -_provider: DataProvider
        +get(ticker, start, end, granularity) FetchResult
    }
    class RefreshHelper {
        <<module>>
        +refresh_tickers(tickers, cache, provider, granularity) RefreshSummary
        +refresh_cached(cache, provider, granularity) RefreshSummary
        +refresh_universe(name, cache, provider, granularity) RefreshSummary
        +refresh_all(cache, provider, granularity) RefreshSummary
    }
    class RefreshResult {
        +ticker: str
        +status: str
        +bars_added: int
        +error_message: str | None
        +duration_seconds: float
    }
    class RefreshSummary {
        +total: int
        +updated: int
        +unchanged: int
        +errors: int
        +duration_seconds: float
        +details: list~RefreshResult~
    }
    class DataCLI {
        <<module>>
        +main(argv) int
        +refresh subcommand
    }
    class CacheTab {
        <<UI: Streamlit>>
        +mode: RadioOption
        +universe: Dropdown
        +ticker_input: TextInput
        +button: Button "Refresh starten"
        +render_progress(summaries) None
    }
    class BacktestDashboard {
        +tabs: RunForm / ReadMode / Vergleich / Cache
    }

    ParquetCache --> DataService
    ParquetCache --> RefreshHelper
    RefreshHelper --> RefreshSummary
    RefreshSummary --> RefreshResult
    RefreshHelper --> ProviderChain
    DataCLI --> RefreshHelper
    BacktestDashboard --> CacheTab
    CacheTab --> RefreshHelper
```

## Flow

```mermaid
flowchart TD
    A([Streamlit: User klickt Cache-Tab]) --> B[Render Sidebar mit 3 Optionen]
    B --> C{Mode?}
    C -->|alle gecachten| D[cache.list_cached_tickers daily]
    C -->|Universe| E[PresetRepository.get + tickers]
    C -->|Ticker-Liste| F[parse TextInput comma-separated]
    D --> G[RefreshHelper.refresh_X t1, t2, t3, ...]
    E --> G
    F --> G
    G --> H[pro Ticker: Cache.covers_range start, end]
    H --> I{fully covered?}
    I -->|yes| J[status=unchanged, bars_added=0]
    I -->|no| K[berechne missing ranges, fetch via Provider-Chain]
    K --> L{provider OK?}
    L -->|yes| M[Cache.merge_incremental ticker, granularity, new_bars]
    L -->|no| N[status=error, error_message=reason]
    M --> O[status=updated, bars_added=count]
    O --> P[naechster Ticker]
    J --> P
    N --> P
    P --> Q{alle Tickers prozessiert?}
    Q -->|no| H
    Q -->|yes| R[RefreshSummary aggregiert]
    R --> S[st.dataframe summary.details]
    R --> T[st.success N updated, M unchanged, K errors in Xs]

    U([CLI: python -m quant_trader.data refresh --tickers SPY,AGG]) --> V[DataCLI.refresh]
    V --> G
```

## Sequence

```mermaid
sequenceDiagram
    actor U as User
    participant D as BacktestDashboard (Cache Tab)
    participant RH as RefreshHelper
    participant Cache as ParquetCache
    participant PC as ProviderChain (FMP + Fallbacks)
    participant Log as structlog

    U->>D: klickt Cache-Tab, waehlt "Ticker-Liste", "SPY,AGG", klickt "Refresh starten"
    D->>RH: refresh_tickers([SPY, AGG], cache, provider_chain, DAILY)

    loop pro Ticker (SPY, dann AGG)
        RH->>Cache: covers_range(SPY, DAILY, start, end)
        Cache-->>RH: (False, 2024-06-28, 2024-06-28) -- stale

        RH->>PC: fetch(SPY, start, end) -- ueberspringt 2024-06-28 bis gestern
        PC-->>RH: list[Bar] (1273 neue)
        RH->>Cache: merge_incremental(SPY, DAILY, new_bars)
        Cache->>Cache: read existing (bis 2024-06-28)
        Cache->>Cache: concat + dedup + sort
        Cache->>Cache: write parquet
        Cache-->>RH: path
        RH->>Log: data.refresh.ticker ticker=SPY updated bars_added=1273 duration=3.4s
    end

    RH-->>D: RefreshSummary(total=2, updated=2, unchanged=0, errors=0, duration=7.2s)
    D->>D: st.dataframe(summary.details)
    D->>D: st.success("2 Tickers refreshed")
    D->>Log: data.refresh.complete total=2 updated=2
```

## Notes

- **Inkrement-Update**: `merge_incremental` macht full rewrite mit DEDUP;
  NICHT echtes append (parquet hat kein effizientes append), aber
  für tägliche Updates (1 Bar/Tag) ist die Full-Rewrite-Groesse minimal
- **Cache-Hit-Erkennung**: `covers_range` liefert `(fully_covered, min, max)`;
  wenn `start >= min AND end <= max`: kein Fetch noetig (NFR-Perf-2)
- **Error-Handling**: pro Ticker isoliert; ein fehlgeschlagener Ticker
  blockiert die anderen nicht (try/except um die Ticker-Schleife)
- **Performance**: FMP Free-Tier (250 calls/Tag) erlaubt ~250 Tickers
  Refresh pro Tag
- **UI-Pattern**: `st.tabs([...])` mit neuem Tab "Cache", analog zu Slice 3.5 Pattern
- **Backward-Compat**: `provider.fetch()` und `cache.write()` unveraendert,
  neue Methoden als Add-On
- **Dashboard**: nutzt `RefreshHelper` direkt (kein separater Background-Task)
