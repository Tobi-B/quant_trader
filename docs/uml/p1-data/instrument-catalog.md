# UML: Slice 1.7 - Zentraler Instrumentkatalog und dynamische Universen

Status:    APPROVED
Phase:     P1 Datenlayer (Erweiterung)
Slice:     1.7 Instrumentkatalog und dynamische Universen
Approved:  2026-08-27

Mapped Requirements:
- NFR-Data-4: Taeglicher Instrumentkatalog mit Fallback auf letzten
  erfolgreichen Snapshot - DRAFT
- NFR-Data-3: FMP bleibt Primary Provider (Free-Tier 250 calls/Tag)
- NFR-Rel-1: Catalog-Refresh ist idempotent (Snapshot ersetzt, kein Append)
- NFR-Obs-1: Strukturiertes Logging (`catalog.*`, `universe.dynamic.*`)
- NFR-Ux-1: Deutsche UI-Texte im Katalog-Tab
- NFR-Sec-1: FMP-Key ausschliesslich aus `.env`

Stories:
- US-P1.10 Vollstaendigen Instrumentkatalog durchsuchen
- US-P1.11 Universen aus dem Katalog erstellen
- US-P1.12 Standard-Universen dynamisch aktuell halten
- US-P1.13 Taegliche Aktualisierung mit verlaesslichem Fallback

Referenz: ADR-0018, PRD `docs/prd/p1-data/instrument-catalog.md`.
Erweitert `FinancialModellingPrepProvider` (Slice 1.5, ADR-0009) und die
Universe-Resolution in `BacktestOrchestrator`/`DashboardRunner` (Slice 1.1).
`PresetRepository`/`UniverseStore` bleiben unveraendert erhalten.

## Structure

```mermaid
classDiagram
    class Instrument {
        +ticker: str
        +name: str
        +exchange: str
        +currency: str
        +instrument_type: str = ""
        +country: str = ""
        +sector: str = ""
        +exchange_full_name: str = ""
        +is_active: bool = True
    }
    class InstrumentSnapshotMeta {
        +snapshot_id: str
        +built_at: datetime
        +source: str
        +total: int
    }
    class FinancialModellingPrepProvider {
        +search(query) list~Instrument~
        +fetch_stock_list() list~Instrument~
        +fetch_etf_list() list~Instrument~
        +fetch_fund_list() list~Instrument~
        +fetch_index_list() list~Instrument~
        +fetch_crypto_list() list~Instrument~
        +fetch_exchanges() list~ExchangeDescriptor~
        +fetch_sectors() list~str~
        +fetch_countries() list~str~
        +fetch_index_membership(index_id) list~str~
    }
    class InstrumentCatalogSnapshotStore {
        -_path: Path
        +exists() bool
        +read() DataFrame | None
        +write(df, snapshot_id) None
        +path_for() Path
        +latest_snapshot_id() str | None
        +snapshot_age() timedelta | None
        +needs_refresh(max_age) bool
    }
    class InstrumentCatalogService {
        -_provider: FinancialModellingPrepProvider
        -_store: InstrumentCatalogSnapshotStore
        -_refresh_interval: timedelta
        +refresh(force) CatalogRefreshResult
        +search(query, filters, limit) list~Instrument~
        +list_filter_options() FilterOptions
        +snapshot_status() CatalogStatus
        +build_dynamic_universe(name, filters) DynamicUniverse
        +build_standard_universe(name) DynamicUniverse
    }
    class CatalogUnavailableError {
        +last_snapshot_id: str | None
        +reason: str
    }
    class CatalogRefreshError {
        +provider: str
        +reason: str
    }
    class DynamicUniverseStore {
        -_base_dir: Path
        +path_for(name) Path
        +exists(name) bool
        +save(payload, overwrite) None
        +load(name) DynamicUniverse
        +list_loaded() list~str~
    }
    class DynamicUniverse {
        +name: str
        +built_from_snapshot: str
        +created_at: datetime
        +filter_description: str
        +filters: dict
        +tickers: tuple~str~
    }
    class UniverseAlreadyExistsError
    class PresetRepository {
        +load(name) Preset
    }
    class Settings {
        +catalog_path: Path
        +dynamic_universes_path: Path
        +catalog_max_age_hours: int = 24
    }
    class BacktestOrchestrator {
        -_resolve_multi_tickers(strategy, universe) list~str~
    }
    class DashboardRunner {
        -_resolve_ticker(...) tuple
    }
    class KatalogTab["Dashboard: Katalog-Tab"] {
        +_render_catalog_tab(catalog_service, dynamic_store)
    }

    InstrumentCatalogService --> FinancialModellingPrepProvider : provider
    InstrumentCatalogService --> InstrumentCatalogSnapshotStore : store
    InstrumentCatalogService --> DynamicUniverseStore : builds into
    InstrumentCatalogService ..> CatalogUnavailableError : raises
    InstrumentCatalogService ..> CatalogRefreshError : raises
    InstrumentCatalogSnapshotStore --> Instrument : persists
    InstrumentCatalogSnapshotStore --> InstrumentSnapshotMeta : tags
    DynamicUniverseStore --> DynamicUniverse : persists
    DynamicUniverseStore ..> UniverseAlreadyExistsError : raises
    Settings --> InstrumentCatalogSnapshotStore : catalog_path
    Settings --> DynamicUniverseStore : dynamic_universes_path
    BacktestOrchestrator --> PresetRepository : 1. lookup
    BacktestOrchestrator --> DynamicUniverseStore : 2. fallback lookup
    DashboardRunner --> PresetRepository : 1. lookup
    DashboardRunner --> DynamicUniverseStore : 2. fallback lookup
    KatalogTab --> InstrumentCatalogService
    KatalogTab --> DynamicUniverseStore
```

## Flow

```mermaid
flowchart TD
    A([Katalog-Tab geoeffnet oder CLI: catalog refresh]) --> B{store.needs_refresh?}
    B -->|nein, Snapshot < 24h| C[snapshot_status: aktuell]
    C --> Z1([Suche/Filter direkt auf Snapshot])

    B -->|ja| D[provider: stock/etf/fund/index/crypto-list + exchanges/sectors/countries]
    D --> E{alle Calls ok?}
    E -->|ja| F[dedupe by ticker+exchange+currency]
    F --> G[store.write: temp-Datei + os.replace]
    G --> H[log catalog.refresh.complete]
    H --> Z1

    E -->|RateLimitedError / ProviderError| I{store.exists?}
    I -->|ja, alter Snapshot vorhanden| J[log catalog.refresh.fallback]
    J --> K[st.warning: letzte Aktualisierung TS]
    K --> Z1
    I -->|nein, kein Snapshot| L[raise CatalogUnavailableError]
    L --> Z2([UI: deutsche Fehlermeldung, keine Suche moeglich])

    Z1 --> M{Nutzeraktion}
    M -->|Suche/Filter| N[service.search query, filters]
    N --> O[Ergebnis-Tabelle Symbol/Name/Boerse/Land/Typ]
    M -->|Standard-Universe Button sp500/etfs| P[service.build_standard_universe]
    P --> Q[fetch_index_membership vs stock_list Schnittmenge]
    Q --> R[DynamicUniverseStore.save overwrite=false]
    M -->|In Universe uebernehmen| S[Name eingeben, Speichern]
    S --> T{DynamicUniverseStore.exists name?}
    T -->|nein| R
    T -->|ja| U[st.warning: Existiert bereits. Ersetzen?]
    U -->|bestaetigt| V[save overwrite=true]
    U -->|abgebrochen| Z1
    R --> W([Universe waehlbar in Backtest-Konfiguration])
    V --> W
```

## Sequence

```mermaid
sequenceDiagram
    actor U as Trader
    participant Tab as Katalog-Tab
    participant Svc as InstrumentCatalogService
    participant Store as InstrumentCatalogSnapshotStore
    participant FMP as FinancialModellingPrepProvider
    participant API as FMP-API
    participant DUS as DynamicUniverseStore

    U->>Tab: Katalog-Tab oeffnen
    Tab->>Svc: snapshot_status()
    Svc->>Store: needs_refresh(24h)
    Store-->>Svc: true (kein Snapshot heute)
    Svc->>FMP: fetch_stock_list(), fetch_etf_list(), ...
    FMP->>API: GET /stable/stock-list?apikey=XXX (+ 8 weitere Calls)
    API-->>FMP: 200 [...]
    FMP-->>Svc: list[Instrument] je Endpoint
    Svc->>Svc: dedupe by (ticker, exchange, currency)
    Svc->>Store: write(df, snapshot_id)
    Store-->>Svc: ok (temp + os.replace)
    Svc-->>Tab: CatalogStatus(total, snapshot_id, aktuell)

    U->>Tab: Suche "BRK.B"
    Tab->>Svc: search("BRK.B", filters={})
    Svc->>Store: read()
    Store-->>Svc: DataFrame
    Svc->>Svc: query.strip().upper() gegen ticker/name
    Svc-->>Tab: [Instrument(BRK.B, Berkshire Hathaway B, NYSE, USD, ...)]
    Tab-->>U: Ergebnis-Tabelle

    U->>Tab: Auswahl -> Name "us_conglomerates" -> Speichern
    Tab->>DUS: exists("us_conglomerates")
    DUS-->>Tab: false
    Tab->>DUS: save(payload, overwrite=false)
    DUS-->>Tab: ok
    Tab-->>U: Universe gespeichert, waehlbar im Backtest

    alt Refresh schlaegt fehl, alter Snapshot vorhanden
        Svc->>FMP: fetch_stock_list()
        FMP-->>Svc: RateLimitedError("Limit Reach")
        Svc->>Store: exists()
        Store-->>Svc: true
        Svc->>Svc: log catalog.refresh.fallback
        Svc-->>Tab: CatalogStatus(total, snapshot_id, veraltet, age)
        Tab-->>U: st.warning("Letzte Aktualisierung: {ts}")
    end

    alt Refresh schlaegt fehl, kein Snapshot vorhanden
        Svc->>FMP: fetch_stock_list()
        FMP-->>Svc: ProviderError("network: ...")
        Svc->>Store: exists()
        Store-->>Svc: false
        Svc-->>Tab: raise CatalogUnavailableError
        Tab-->>U: deutsche Fehlermeldung, keine Suche moeglich
    end
```

## Notes

- Snapshot-Schreiben ist atomar (`temp` + `os.replace`), damit ein
  abgebrochener Refresh (z.B. Prozessabbruch waehrend `fetch_index_list`)
  nie eine halbe/kaputte Parquet-Datei hinterlaesst - `read()` sieht
  entweder den alten oder den vollstaendig neuen Snapshot, nie einen
  Zwischenstand.
- `needs_refresh` vergleicht `snapshot_age()` gegen
  `Settings.catalog_max_age_hours` (Default 24h); ein Refresh laeuft
  hoechstens einmal pro Tag automatisch, manuell jederzeit via
  `catalog refresh --force`.
- `DynamicUniverse.tickers` ist eine feste Momentaufnahme zum
  Speicherzeitpunkt (kein Live-Rebuild bei Katalog-Refresh) - konsistent
  zu bestehendem `UniverseStore`-Verhalten.
- `build_standard_universe("sp500"|"etfs")` nutzt denselben
  `save(overwrite=True)`-Pfad wie ein manuell gespeichertes Universe;
  `dax40` bleibt ausschliesslich in `PresetRepository` (kein FMP-Call).
- Resolution-Reihenfolge in `BacktestOrchestrator`/`DashboardRunner`
  bleibt `PresetRepository` zuerst, `DynamicUniverseStore` als Fallback -
  bestehende Backtests mit statischen Presets sind unveraendert.
- `CatalogUnavailableError` wird in der UI gezielt gefangen (deutsche
  Meldung); alle anderen `DataError`-Subklassen propagieren wie bisher.
