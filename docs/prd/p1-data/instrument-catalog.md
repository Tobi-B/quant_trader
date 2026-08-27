# PRD: Slice 1.7 - Zentraler Instrumentkatalog und dynamische Universen

Phase:    P1 Datenlayer (Erweiterung)
Slice:    1.7 Instrumentkatalog und dynamische Universen
Status:   DRAFT
Author:   opencode
Created:  2026-07-19
Updated:  2026-07-19

## Goal

Den FMP-basierenden Datenlayer um einen zentralen, taeglich aktualisierten
Instrumentkatalog erweitern, aus dem heraus Trader mit Sonderzeichen-Symbolen
wie `BRK.B`, allen fuenf Asset-Klassen (Aktien, ETFs, Fonds, Indizes, Krypto)
sowie Filter- und Auswahlmoeglichkeiten suchen und benannte, wiederverwendbare
Universen erstellen koennen. Die bestehenden Standard-Presets `sp500`, `dax40`
und `etfs` sollen weiterhin auswaehlbar bleiben; `sp500` und `etfs` werden aus
dem Katalog aufgebaut, `dax40` bleibt statisch (kein DAX-Constituents-Endpoint
bei FMP).

## Scope (IN)

- `src/quant_trader/data/financial_modelling_prep.py` (ERWEITERN):
  - Neue Public-Methoden auf `FinancialModellingPrepProvider`:
    - `fetch_stock_list() -> list[Instrument]` (Stable: `/stable/stock-list`)
    - `fetch_etf_list() -> list[Instrument]` (Stable: `/stable/etf-list`)
    - `fetch_fund_list() -> list[Instrument]` (Stable:
      `/stable/financial-statement-symbol-list`, leer im Free-Tier mit Hinweis)
    - `fetch_index_list() -> list[Instrument]` (Stable: `/stable/index-list`)
    - `fetch_crypto_list() -> list[Instrument]` (Stable:
      `/stable/cryptocurrency-list`)
    - `fetch_exchanges() -> list[ExchangeDescriptor]` (Stable:
      `/stable/available-exchanges`)
    - `fetch_sectors() -> list[str]` (Stable: `/stable/available-sectors`)
    - `fetch_countries() -> list[str]` (Stable: `/stable/available-countries`)
    - `fetch_index_membership(index_id) -> list[str]` (Stable:
      `/stable/{sp500|nasdaq|dowjones}-constituent`)
  - Method-Implementierungen folgen dem URL-Bau-, Error- und
    Logging-Pattern aus `search()` (ADR-0017) und `fetch()` (ADR-0009).
- `src/quant_trader/core/types.py` (ERWEITERN):
  - `Instrument` um optionale Felder `instrument_type`, `country`, `sector`,
    `exchange_full_name`, `is_active` mit Default `""` bzw. `True` ergaenzen.
    Bestehende Konstruktionen (z.B. `_parse_search_results`) bleiben unveraendert
    gueltig.
  - Neue frozen dataclass `InstrumentSnapshotMeta` mit `snapshot_id`,
    `built_at`, `source`, `total`.
- `src/quant_trader/core/errors.py` (ERWEITERN):
  - `CatalogUnavailableError(DataError)` mit `last_snapshot_id` und `reason`.
  - `CatalogRefreshError(DataError)` mit `provider` und `reason`.
- `src/quant_trader/core/config.py` (ERWEITERN):
  - `catalog_path: Path = Path("./data/catalog/instruments.parquet")`.
  - `dynamic_universes_path: Path = Path("./data/universe")`.
  - `catalog_max_age_hours: int = 24`.
- `src/quant_trader/data/instrument_catalog.py` (NEU):
  - `InstrumentCatalogSnapshotStore` mit `path_for()`, `exists()`, `read()`,
    `write(df, snapshot_id)` (atomic via `temp + os.replace`),
    `latest_snapshot_id()`, `snapshot_age()`, `needs_refresh(max_age)`.
  - `InstrumentCatalogService(provider, store, refresh_interval)` mit
    `refresh(*, force=False)`, `search(query, **filters)`,
    `list_filter_options()`, `snapshot_status()`,
    `build_dynamic_universe(name, filters)` und
    `build_standard_universe(name)`.
  - Strukturiertes Logging: `catalog.refresh.start`, `.provider`,
    `.complete`, `.fallback`, `.unavailable`, `catalog.search.start`,
    `.complete`, `catalog.snapshot.built`, `catalog.snapshot.used`.
- `src/quant_trader/universe/dynamic_store.py` (NEU):
  - `DynamicUniverseStore(base_dir)` mit `path_for(name)`,
    `exists(name)`, `save(payload, *, overwrite=False)`,
    `load(name)`, `list_loaded()`.
  - JSON-Serialisierung mit Schema aus ADR-0018 (Abschnitt 4).
  - `UniverseAlreadyExistsError` als spezifische Exception.
- `src/quant_trader/universe/cli.py` (ERWEITERN):
  - Neuer Subcommand `catalog` mit `refresh`, `status`, `list`.
  - Neuer Subcommand `universe` mit `save`, `list`, `load` (JSON/CSV
    kombiniert).
  - Strukturiertes Logging in deutscher CLI-Ausgabe.
- `src/quant_trader/universe/__init__.py` (ERWEITERN):
  - Re-Export `DynamicUniverseStore`, `DynamicUniverse`,
    `UniverseAlreadyExistsError`.
- `src/quant_trader/universe/loader.py` (UNVERAENDERT): wird durch
  Service-Layer im Dashboard umgangen; Backtest-Orchestrator und
  `DashboardRunner` muessen nicht angefasst werden, weil die Resolution in
  deren `_resolve_*` um den `DynamicUniverseStore`-Lookup ergaenzt wird.
- `src/quant_trader/backtest/orchestrator.py` (ERWEITERN):
  - `_resolve_multi_tickers` prueft zuerst `PresetRepository`, dann
    `DynamicUniverseStore`.
- `src/quant_trader/backtest/dashboard_runner.py` (ERWEITERN):
  - `_resolve_ticker` analog: `PresetRepository` zuerst,
    `DynamicUniverseStore` als Fallback.
- `scripts/backtest_dashboard.py` (ERWEITERN):
  - Neuer Tab "Katalog" zwischen "Cache" und "Strategien".
  - `_render_catalog_tab(catalog_service, dynamic_store)`:
    - `snapshot_status` mit `st.caption` und `st.warning` (bei veraltetem
      Snapshot).
    - Multiselects fuer Instrumentart, Land, Boerse, Sektor, Index
      (alle mit `key=`).
    - Suchfeld und Result-Tabelle.
    - "In Universe uebernehmen" mit Bestaetigungsdialog bei Namenskonflikt.
    - Standard-Universen-Buttons fuer `sp500` (dynamisch), `dax40` (statisch
      via Preset, Hinweis), `etfs` (dynamisch).
  - `_build_services()` instanziiert `InstrumentCatalogService` und
    `DynamicUniverseStore` ueber `@st.cache_resource`.
- `tests/data/test_catalog_provider.py` (NEU): mind. 6 Tests mit
  `_FakeSession` (Pattern aus `tests/data/test_financial_modelling_prep.py`).
  URL-Asserts auf alle neuen Endpoints, `HTTP 429` -> `RateLimitedError`,
  Netzwerkfehler -> `ProviderError`, `HTTP 403` -> `ProviderError`.
- `tests/data/test_catalog_store.py` (NEU): mind. 4 Tests. Atomares
  Schreiben (Temp-Datei + `os.replace`), Roundtrip, `needs_refresh`
  Grenzwerte, `snapshot_age` bei fehlender Datei.
- `tests/data/test_catalog_service.py` (NEU): mind. 8 Tests mit
  `FakeCatalogProvider`. `refresh` aggregiert `CatalogRefreshResult`,
  `search` mit Filtern (type, country, exchange, sector, query), `search`
  bounded limit, `snapshot_status`, `search` mit `BRK.B` findet das
  Instrument, Refresh-Fehler ohne Snapshot -> `CatalogUnavailableError`,
  Refresh-Fehler mit Snapshot -> Fallback-Snapshot.
- `tests/universe/test_dynamic_store.py` (NEU): mind. 5 Tests. `save`
  ohne overwrite verweigert, `save` mit overwrite ersetzt, `load`
  liefert Dataclass, `list_loaded` sortiert, parent directories werden
  angelegt.
- `tests/test_dashboard_catalog.py` (NEU): Source-Inspection wie
  `tests/test_dashboard_company_search.py` und neue Asserts auf `key=` an
  jedem `st.multiselect` (verwendet Pattern aus
  `tests/test_dashboard_smoke.py`).
- `docs/architecture.md` (ERWEITERN): Module-Tabelle um
  `InstrumentCatalogService`, `DynamicUniverseStore`. Datenfluss-Skizze um
  den Katalogpfad.
- `docs/STATE.md` (ERWEITERN): Phase-Tag `p1-data/1.7` mit Status `DRAFT`,
  nach Implementation auf `DONE`.
- `docs/requirements/nfrs.md` (ERWEITERN): Neue Zeile `NFR-Data-4`
  (DRAFT) mit Verweis auf ADR-0018.
- `docs/adr/0018-instrument-catalog-and-dynamic-universes.md` (NEU,
  Status `accepted` nach Implementation).

## Out of Scope (verbindlich)

- Auto-Refresh bei Backtest-Start, Cron, Scheduled-Jobs.
- File-Lock fuer parallele Schreibprozesse.
- Snapshot-Rotation (`data/catalog/snapshots/<id>.parquet`).
- Mutual-Fund-Liste (Free-Tier nicht verfuegbar, siehe ADR-0018).
- DAX-40-Konstruktion aus dynamischen Quellen.
- Profil-/Bulk-Profile-Anreicherung fuer Sektor/Land.
- ISIN/CUSIP/CIK-Suche als Dashboard-Tab (kommt in spaeterem Slice).
- Concurrent Dashboard-Sessions (Multi-User, Locking).
- Wechsel des Primärproviders (z.B. OpenFIGI, CoinGecko).
- Tickersuche via KI/NLP.

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies ausserhalb `pyproject.toml`.
- Kein `print`, kein globaler State, kein Wildcard-Import.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Sprache: Code/Logs englisch, CLI/UI-Strings deutsch (NFR-Ux-1).
- Alle 519 bestehenden Tests unveraendert gruen.
- `Instrument`-Erweiterung ist additiv (Defaults erhalten).
- Persistenzpfade ausschliesslich aus `Settings` (kein Hardcoding).
- `key=` auf jedem `st.selectbox`/`st.multiselect`/`st.radio` im
  Dashboard (Test `test_dashboard_selectboxes_have_unique_keys`).
- Strukturiertes Logging via `structlog`, keine `print`-Calls.
- Code-Reproducibility: alle Tests via `make test` reproduzierbar, ohne
  Live-API-Calls.

## Mapped NFRs

- NFR-Data-1: Parquet-Cache bleibt unveraendert; Universe-Aufloesung
  delegiert weiterhin an `DataService` und `ParquetCache`.
- NFR-Data-3: FMP bleibt Primary Provider (Free-Tier 250 calls/Tag);
  Catalog-Refresh verbraucht ~12 Calls/Tag.
- NFR-Data-4 (NEU, DRAFT): Taeglicher Instrumentkatalog mit Fallback auf
  letzten erfolgreichen Snapshot.
- NFR-Rel-1: Catalog-Refresh ist idempotent (Snapshot ersetzt, kein
  Append).
- NFR-Obs-1: Strukturiertes Logging fuer `catalog.refresh.*`,
  `catalog.search.*`, `universe.dynamic.*`.
- NFR-Ux-1: Deutsche UI-Texte im neuen Katalog-Tab.
- NFR-Sec-1: FMP-Key ausschliesslich aus `.env`.

## UML-Referenz

Visualisiert in: `docs/uml/p1-data/instrument-catalog.md` (Status: DRAFT,
wird mit diesem Slice auf APPROVED gesetzt).

## Done when

- [ ] `FinancialModellingPrepProvider` um die Catalog-Methoden erweitert
- [ ] `Instrument` um optionale Felder ergaenzt, Backward-Compat gewahrt
- [ ] `CatalogUnavailableError` und `CatalogRefreshError` in
      `core/errors.py` definiert
- [ ] `catalog_path`, `dynamic_universes_path`, `catalog_max_age_hours`
      in `Settings`
- [ ] `InstrumentCatalogSnapshotStore` mit atomarem Schreiben implementiert
- [ ] `InstrumentCatalogService` mit `refresh`, `search`,
      `list_filter_options`, `snapshot_status`,
      `build_dynamic_universe`, `build_standard_universe` implementiert
- [ ] `DynamicUniverseStore` mit JSON-Persistenz implementiert
- [ ] Universe-Resolution in `BacktestOrchestrator` und `DashboardRunner`
      ergaenzt
- [ ] Dashboard-Tab "Katalog" mit Suche, Filter, Speichern und
      Standard-Universen-Buttons
- [ ] CLI-Subcommands `catalog refresh/status/list` und
      `universe save/load/list` implementiert
- [ ] Tests in `tests/data/test_catalog_*.py` und
      `tests/universe/test_dynamic_store.py` mit mind. 23 neuen Tests
- [ ] Dashboard-Smoke-Tests fuer `key=` und Catalog-Tab-Inhalte
- [ ] `make test` gruen (519 alte + mind. 23 neue Tests)
- [ ] `make lint` gruen
- [ ] `make smoke` gruen
- [ ] ADR-0018 Status `proposed` -> `accepted`
- [ ] `docs/STATE.md` aktualisiert (Slice 1.7 auf DONE)
- [ ] Conventional Commits: `docs(p1-data)`, `feat(p1-data)`,
      `test(p1-data)` (Small Commits erlaubt)

## Anti-Drift-Reminder

Vor dem Coden:

```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p1-data/instrument-catalog.md
cat docs/uml/p1-data/instrument-catalog.md
cat docs/prd/p1-data/instrument-catalog.md
cat docs/adr/0018-instrument-catalog-and-dynamic-universes.md
cat docs/adr/0009-fmp-as-primary-provider.md
cat docs/adr/0017-company-search-via-fmp.md
```

Waehrend des Codens:

- Tue **nur** das, was in `Scope (IN)` steht.
- Mutual-Fund-Liste bleibt leer im Free-Tier (kein Mocking).
- `BRK.B` muss ohne Phantom-Filter direkt gefunden werden.
- `key=` auf jedem neuen `selectbox`/`multiselect`/`radio`.
- Bestehende 519 Tests unveraendert gruen.

Nach dem Coden:

- Conventional Commits: `docs(p1-data)`, `feat(p1-data): slice 1.7 ...`,
  ggf. `test(p1-data)`.
- Commit-Body enthaelt: warum atomares Schreiben (Parquet-Konsistenz),
  warum `dax40` statisch (kein FMP-DAX-Constituents-Endpoint),
  warum 12 Calls Budget im 250er Free-Tier.
