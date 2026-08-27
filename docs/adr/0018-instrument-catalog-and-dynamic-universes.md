# ADR 0018: Zentraler Instrumentkatalog und dynamische Standard-Universen

Status:     proposed
Datum:      2026-07-19
Phase:      P1 Datenlayer (Erweiterung)
Supersedes: -
Superseded by: -

## Context

Slice 3.7 hat die FMP-Suche ueber den Endpoint `/stable/search-name` eingefuehrt
(siehe ADR-0017). Trader berichten, dass die Suche fuer bekannte Symbole wie
`BRK.B` zu "nicht gefunden" fuehrt, obwohl das Instrument existiert. Begruendung:

- `/stable/search-name` ist eine Volltextsuche ueber Instrumentnamen. Ticker mit
  Sonderzeichen wie `.` (z.B. `BRK.B`) oder `-` (z.B. `BRK-B`) werden in der
  FMP-Suche inkonsistent behandelt, weil FMP sie als separate Spalten fuehrt.
- Die Suche kennt nur die freigegebenen Felder aus `/stable/search-name`
  (`symbol`, `name`, `exchange`, `exchangeFullName`, `currency`) und liefert
  keinen Instrumenttyp, kein Land und keinen Sektor.
- Existierende statische Universe-Presets (`sp500`, `dax40`, `etfs`) in
  `config/universe_presets.yaml` sind handgepflegt und driften; sie koennen
  nicht dynamisch um neue Listings, Ticker-Umbenennungen oder Indexrebalancings
  erweitert werden.

Traderwuensche (User-Story-Interview 2026-07-19):

- **Vollstaendiger Instrumentkatalog**: alle bei FMP gelisteten Aktien, ETFs,
  Fonds, Indizes und Kryptowaehrungen sollen suchbar sein; `BRK.B` und
  aehnliche Sonderzeichen-Symbole muessen direkt gefunden werden.
- **Universen aus dem Katalog**: Trader wollen Instrumente nach Index, Boerse,
  Land, Sektor und Instrumentart filtern oder einzeln auswaehlen und als
  benannte, wiederverwendbare Universen speichern.
- **Standard-Universen dynamisch**: `sp500`, `dax40` und `etfs` sollen sich aus
  dem aktuellen Katalog zusammensetzen; bestehende Namen bleiben auswaehlbar.
  `dax40` bleibt wegen fehlender FMP-Constituents-Liste statisch.
- **Taegliche Aktualisierung**: Der Katalog soll taeglich aktuell sein; bei
  Ausfall bleibt der letzte erfolgreiche Stand verfuegbar.

Im Repo vorhanden:

- `FinancialModellingPrepProvider` (Slice 1.5) mit `search()` und `fetch()`.
- `Instrument` als frozen Dataclass in `core/types.py`.
- `PresetRepository` (YAML) und `UniverseStore` (CSV) aus Slice 1.1.
- `BacktestOrchestrator._resolve_multi_tickers` und `DashboardRunner._resolve_ticker`
  lesen Universe-Presets heute ueber `PresetRepository`.
- `Dashboard`-Tabs (Slices 3.3, 3.5, 3.6, 1.6, 2.6, 3.7, 3.8).

## Decision

### 1. Neuer Provider-Slice in FMP

`FinancialModellingPrepProvider` (in `src/quant_trader/data/financial_modelling_prep.py`)
bekommt catalog-bezogene Public-Methoden, die den jeweils passenden `/stable/`
Endpoint mit `apikey` aufrufen. Pattern ist 1:1 zu `search()` und folgt
ADR-0009. Methoden:

- `fetch_stock_list() -> list[Instrument]` (`/stable/stock-list`)
- `fetch_etf_list() -> list[Instrument]` (`/stable/etf-list`)
- `fetch_fund_list() -> list[Instrument]` (`/stable/financial-statement-symbol-list`,
  optional via `isFund`-Heuristik ueber `/stable/profile`)
- `fetch_index_list() -> list[Instrument]` (`/stable/index-list`)
- `fetch_crypto_list() -> list[Instrument]` (`/stable/cryptocurrency-list`)
- `fetch_exchanges() -> list[ExchangeDescriptor]` (`/stable/available-exchanges`)
- `fetch_sectors() -> list[str]` (`/stable/available-sectors`)
- `fetch_countries() -> list[str]` (`/stable/available-countries`)
- `fetch_index_membership(index_id) -> list[str]` (`/stable/{sp500|nasdaq|dowjones}-constituent`)

Begruendung:
- FMP ist bereits Primary Provider (NFR-Data-3).
- Stable-Endpoints sind seit August 2025 verpflichtend (ADR-0017).
- Free-Tier verfuegbar fuer die gelisteten Endpoints (siehe FMP-Pricing-Tabelle,
  z.B. S&P 500/Nasdaq/Dow-Constituents sind im Basic-Plan enthalten).

Mutual Funds sind im FMP Free-Tier nicht als Liste verfuegbar; die
Methode `fetch_fund_list` liefert eine leere Liste mit dokumentiertem Hinweis
("Fonds nicht im Free-Tier verfuegbar"). Begruendung: Free-Tier unterstuetzt
keine Mutual-Fund-Liste (siehe FMP-Pricing; nur Ultimate enthaelt Holdings).

### 2. Catalog-Service

Neues Modul `src/quant_trader/data/instrument_catalog.py` mit:

- `InstrumentCatalogService(provider, store, refresh_interval=timedelta(days=1))`
- Methoden:
  - `refresh(*, force=False) -> CatalogRefreshResult`: ruft die oben definierten
    FMP-Methoden auf, dedupliziert ueber `(ticker, exchange, currency)`, schreibt
    atomar in den Snapshot-Store, gibt Anzahl hinzugefuegter, entfernter und
    unveraenderter Instrumente zurueck.
  - `search(query, *, limit=50, **filters) -> list[Instrument]`: filtert den
    aktuellen Snapshot; `query.strip().upper()` matched gegen `ticker` und
    `name`. `query` mit `.` (z.B. `BRK.B`) findet das Instrument direkt im
    `ticker`-Feld.
  - `list_filter_options() -> FilterOptions`: liefert aktuelle Werte fuer
    Boersen, Sektoren, Laender, Instrumentarten und Indizes.
  - `snapshot_status() -> CatalogStatus`: Alter des Snapshots, Anzahl
    Instrumente, letzte Quelle.
- Strukturiertes Logging: `catalog.refresh.start`, `.complete`, `.provider`,
  `.fallback` (analog ADR-0017), `catalog.search.start`, `.complete`,
  `catalog.snapshot.unavailable`.
- Atomare Snapshot-Schreibung via `temp + os.replace`, damit ein abgebrochener
  Refresh keine halbe Datei hinterlaesst.
- Fallback-Semantik: Bei `HTTP 429` / `ProviderError` und vorhandenem Snapshot
  wird der bisherige Stand weiter genutzt; nur bei fehlendem Snapshot wird
  `CatalogUnavailableError` geworfen.

### 3. Snapshot-Store

`InstrumentCatalogSnapshotStore` in
`src/quant_trader/data/instrument_catalog.py`:

- Persistenz: `data/catalog/instruments.parquet` (eine Datei, gleiche
  Parquet-Technologie wie der Cache).
- Schema (Spalten):
  `snapshot_id, ticker, name, exchange, exchange_full_name, currency,
   instrument_type, country, sector, is_active, source_index`.
- `snapshot_id = "{ISO-Timestamp}-{UUID-Suffix}"`.
- Methoden: `exists()`, `read() -> DataFrame | None`, `write(df, snapshot_id)`,
  `path_for()`, `latest_snapshot_id()`, `snapshot_age()`, `needs_refresh(max_age)`.
- Persistenzpfad kommt aus `Settings.catalog_path` (Default
  `./data/catalog/instruments.parquet`).

### 4. Universen aus dem Katalog

Dynamische Universen werden ueber einen neuen `DynamicUniverseStore` in
`src/quant_trader/universe/dynamic_store.py` persistiert. Pattern:

- JSON-Datei unter `data/universe/<name>.json` (ein Pfad pro Universe, nicht
  CSV, damit Metadaten wie `built_from_snapshot`, `created_at` und
  `filter_description` mitgespeichert werden koennen).
- Schema:
  ```json
  {
    "name": "us_tech_etfs",
    "built_from_snapshot": "2026-07-19T18:53:00Z-3f2a",
    "created_at": "2026-07-19T18:53:00Z",
    "filter_description": "ETFs in den USA",
    "filters": {"instrument_type": "etf", "country": "US"},
    "tickers": ["SPY", "VOO", "QQQ", "..."]
  }
  ```
- `tickers` ist eine **feste Momentaufnahme** zum Speicherzeitpunkt; bei einer
  folgenden Katalogaktualisierung werden sie nicht automatisch neu berechnet.
  Damit ist das Verhalten konsistent mit `UniverseStore` (idempotent).
- `save(name, payload, *, overwrite=False)` wirft `UniverseAlreadyExistsError`,
  wenn die Datei existiert und `overwrite=False`; bei `overwrite=True` wird
  ersetzt.

Aufloesung in `BacktestOrchestrator._resolve_multi_tickers` und
`DashboardRunner._resolve_ticker`: erst `PresetRepository`, dann
`DynamicUniverseStore`. Reihenfolge bleibt backward-compat fuer bestehende
Backtests.

### 5. Standard-Universen

- `sp500`, `etfs` werden zukuenftig aus dem Katalog gebaut:
  - `sp500`: `fetch_index_membership("sp500")` und Schnittmenge mit `stock_list`.
  - `etfs`: Schnittmenge von `stock_list` mit `etf_list` (oder primaer
    `etf_list`).
- `dax40` bleibt statisch (`config/universe_presets.yaml`), weil FMP keine
  DAX-Constituents-Liste dokumentiert (siehe FMP-Doku; keine Treffer fuer
  "DAX"/"XETRA"/"Frankfurt"/"^GDAXI").
- `PresetRepository` bleibt fuer `dax40` (und alle weiteren statischen
  Listen) erhalten. Migration: dynamische Presets werden ueber einen
  CLI-Subcommand `python -m quant_trader.universe catalog sync` aktualisiert
  und ersetzen den statischen YAML-Eintrag (oder werden parallel als JSON
  gespeichert).

### 6. Dashboard-Tab

Neuer Tab "Katalog" in `scripts/backtest_dashboard.py`, eingefuegt vor
"Strategien". Aufbau:

1. **Status-Anzeige** mit `snapshot_age`, `total`, Quelle. Bei `needs_refresh=True`
   Button "Katalog aktualisieren" sichtbar.
2. **Suche + Filter**: Textfeld fuer Query (z.B. `BRK.B`), Multiselects fuer
   Instrumentart, Land, Boerse, Sektor, Index.
3. **Suchergebnis** als `st.dataframe` (Spalten Symbol, Name, Boerse, Land,
   Instrumentart).
4. **Aktion "In Universe uebernehmen"**: Textfeld fuer Name, Speichern-Button.
   Wenn Name bereits existiert, wird `st.warning("Existiert bereits. Ersetzen?")`
   angezeigt und ein Bestaetigungsbutton rendert das `overwrite=True`-Save.
5. **Standard-Universen** mit Buttons "S&P 500", "ETFs" (dynamisch), "DAX 40"
   (statisch, Hinweis).

Jeder `st.selectbox`/`st.multiselect` bekommt einen expliziten `key=` (Pattern
aus Slice 3.8).

### 7. Performance-Budget und Quota

NFR-Data-3 (250 Calls/Tag Free-Tier) bleibt. Catalog-Refresh verbraucht:

- 5 Listen-Endpunkte (`stock-list`, `etf-list`, `index-list`,
  `cryptocurrency-list`, `financial-statement-symbol-list`) = 5 Calls pro
  Refresh.
- 4 Lookup-Endpunkte (`available-exchanges`, `available-sectors`,
  `available-countries`, `symbol-change`) = 4 Calls.
- 3 Index-Constituents (`sp500-constituent`, `nasdaq-constituent`,
  `dowjones-constituent`) = 3 Calls.
- Total: ~12 Calls pro Refresh; unter 5 % des Tagesbudgets.
- Refresh wird **nur einmal pro Tag** ausgeloest (NFR-Data-4), automatisch
  beim ersten Verwenden oder manuell via CLI `python -m quant_trader.data
  catalog refresh`.

### 8. Fehlerbehandlung

Neue Exception-Hierarchie in `core/errors.py`:

- `CatalogUnavailableError(DataError)`: kein Snapshot verfuegbar und
  Provider-Fehler.
- `CatalogRefreshError(DataError)`: Provider liefert kaputte Daten.

UI faengt nur `CatalogUnavailableError` und zeigt eine deutsche Meldung. Bei
vorhandenem Snapshot + Provider-Fehler wird der alte Snapshot weiter genutzt
und mit `st.warning("Letzte Aktualisierung: {ts}")` annotiert.

## Consequences

**Positiv**

- `BRK.B` und aehnliche Sonderzeichen-Symbole sind direkt suchbar (US-P1.10).
- Trader koennen Universen aus dem Katalog filtern und speichern (US-P1.11).
- Standard-Presets `sp500` und `etfs` werden automatisch aktuell gehalten
  (US-P1.12).
- Taegliche Aktualisierung mit Fallback auf letzten Snapshot (US-P1.13).
- Layer-Trennung bleibt: Provider (FMP) -> Service -> Store -> UI.
- Strukturiertes Logging im Service (NFR-Obs-1).
- Backward-Compat: 519 bestehende Tests unveraendert gruen, dynamische
  Presets nur additiv.

**Negativ**

- FMP Free-Tier (250 Calls/Tag) wird mit Catalog-Calls geteilt.
- Mutual-Fund-Liste ist im Free-Tier nicht verfuegbar; `fetch_fund_list`
  liefert eine leere Liste (ehrliche Out-of-Scope-Info, kein Mocking).
- Snapshot-Datei wachst; bei 50.000 Instrumenten ist sie ~5-10 MB gross,
  Parquet-Read in <500 ms.
- Konkurrente Refresh-Vorgaenge brauchen File-Lock (out-of-scope fuer 1.7;
  CLI und Dashboard serialisieren ueber `st.spinner` bzw. lock-free bei
  Single-User-Anwendung).
- `dax40` bleibt statisch, weil FMP keine Liste dafuer dokumentiert; das ist
  eine ehrliche Luecke, keine versprochene Dynamik, die nicht haelt.

**Neutral**

- `Instrument` wird um optionale Felder (`instrument_type`, `country`,
  `sector`) erweitert; bestehende Konstruktionen bleiben kompatibel
  (Defaults `""`).
- `PresetRepository` bleibt erhalten; dynamische Presets sind ein
  zusaetzlicher Pfad.
- Konfigurationsfelder `catalog_path` und `dynamic_universes_path` werden zu
  `Settings` hinzugefuegt.

## Alternatives Considered

- **OpenFIGI als Katalog-Quelle**: abgelehnt, Free-Tier-Limits, andere
  Felder, mehr Config. FMP bleibt Primary.
- **Snapshot via `delta` Append statt full rewrite**: abgelehnt, weil
  Index-Rebalancings komplex sind und Parquet full-rewrite bei 5-10 MB
  unter 500 ms bleibt.
- **Single-Writer via File-Lock (`fcntl`/`msvcrt`)**: out-of-scope fuer 1.7;
  Single-User-Anwendung.
- **Mutual-Fund-Katalog ueber `cik-list` mit Pagination**: abgelehnt,
  weil `cik-list` nicht als Mutual-Fund-Liste dokumentiert ist und
  Funding-/Filings-Daten liefert, keine Stammdaten.
- **Profile-Bulk fuer Sektor/Land-Anreicherung**: spaetere Optimierung; in 1.7
  reichen die Werte aus `stock-list` und `available-*`-Endpoints.
- **Snapshot-Rotation (`data/catalog/snapshots/<id>.parquet`)**: out-of-scope
  fuer 1.7; nur die aktuelle Datei wird gepflegt. Backtests nutzen die
  Universe-JSON-Datei und tragen `built_from_snapshot` als Audit-Trail.
- **DAX-40-Konstruktion via `company-screener?country=DE`**: abgelehnt,
  Ergebnis ist nicht verifizierbar und kann ETF-Fonds, ADRs oder nicht mehr
  gelistete Werte enthalten. Statisches Preset ist ehrlicher.

## References

- `src/quant_trader/data/financial_modelling_prep.py` (Catalog-Methoden, NEU)
- `src/quant_trader/data/instrument_catalog.py` (NEU)
- `src/quant_trader/data/factory.py` (unveraendert, weil Service-Init im
  Dashboard bleibt)
- `src/quant_trader/core/types.py` (`Instrument` erweitert)
- `src/quant_trader/core/errors.py` (neue Exceptions)
- `src/quant_trader/core/config.py` (`catalog_path`, `dynamic_universes_path`)
- `src/quant_trader/universe/dynamic_store.py` (NEU)
- `src/quant_trader/universe/cli.py` (`catalog refresh`)
- `scripts/backtest_dashboard.py` (Tab "Katalog")
- `tests/data/test_catalog_*.py` (NEU)
- `tests/universe/test_dynamic_store.py` (NEU)
- `docs/userstories/p1-data/instrument-catalog.md` (US-P1.10..US-P1.13)
- `docs/uml/p1-data/instrument-catalog.md` (DRAFT)
- `docs/prd/p1-data/instrument-catalog.md` (DRAFT)
- NFR-Data-3 (FMP Primary Provider)
- NFR-Data-4 (NEU, DRAFT)
- NFR-Sec-1 (API-Key via env)
- NFR-Obs-1 (structlog)
- NFR-Ux-1 (deutsche UI-Texte)
- ADR-0009 (FMP als Primary)
- ADR-0017 (Company Search via FMP)
