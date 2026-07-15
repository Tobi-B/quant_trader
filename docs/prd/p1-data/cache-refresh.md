# PRD: Slice 1.6 - Cache Refresh (Bulk + Inkrementell + Dashboard-UI)

Phase:    P1 Datenlayer (Erweiterung)
Slice:    1.6 Cache Refresh
Status:   DRAFT  (User "starte demo" + "Refresh Button" / "auto-refresh" gilt als implizite Approval; UML auf APPROVED setzen)
Author:   opencode
Created:  2026-07-15
Updated:  2026-07-15

## Goal

Den Parquet-Cache aus Slice 1.2 um zwei Features erweitern:

1. **Inkrement-Update** (US-P1.8): NFR-Data-1 ("Inkrement-Update ohne
   Full-Refetch bei Overlap") ist bereits APPROVED aber bisher nur
   konzeptuell. Jetzt vollstaendig implementieren.
2. **Cache-Refresh-Button im Dashboard** (US-P1.9): Bulk-Refresh fuer
   mehrere Tickers mit drei Optionen (alle gecachten, Universe, freie
   Liste), damit der Trader nicht fuer jeden Ticker einzeln die CLI
   aufrufen muss.

Damit ist der Cache immer aktuell, ohne Cron/Systemd, ohne
Background-Worker, ohne Auto-Refresh-Komplexitaet.

## Scope (IN)

- `src/quant_trader/data/cache.py` (aendern):
  - Neue Methode `merge_incremental(ticker: str, granularity:
    Granularity, new_bars: list[Bar]) -> Path`:
    - Liest existierenden Cache (falls vorhanden) via `read()`
    - Konkateniert existing + new
    - Dedup via set von `(timestamp, ticker)` falls vorhanden
    - Sortiert nach `timestamp` asc
    - Schreibt zurueck (full rewrite mit deduplizierter Union)
    - Falls `new_bars` empty und Cache existiert: no-op, return cache path
    - Log `cache.merge_incremental` mit count-added, count-total
  - Neue Methode `covers_range(ticker: str, granularity: Granularity,
    start: date, end: date) -> tuple[bool, date | None, date | None]`:
    - returnt `(fully_covered, existing_min, existing_max)`
    - wenn fully_covered=True: kein Fetch noetig
    - wenn fully_covered=False: missing range = (start, existing_min) +
      (existing_max, end)
- `src/quant_trader/data/service.py` (aendern):
  - `DataService.get` nutzt `covers_range` und `merge_incremental`:
    - Berechne `covered, cache_min, cache_max = self._cache.covers_range(...)`
    - Wenn `start >= cache_min AND end <= cache_max`: Cache-Hit
    - Sonst: berechne missing-ranges, fetch via Provider-Chain,
      merge_incremental
  - Logging: `data.service.incremental_fetch` mit ranges
- `src/quant_trader/data/refresh.py` (NEU, ~100 Zeilen):
  - `RefreshResult` (frozen dataclass): `ticker`, `status`
    (Literal["updated", "unchanged", "error"]), `bars_added: int`,
    `error_message: str | None`, `duration_seconds: float`
  - `RefreshSummary` (frozen dataclass): `total: int`, `updated: int`,
    `unchanged: int`, `errors: int`, `duration_seconds: float`,
    `details: list[RefreshResult]`
  - `refresh_tickers(tickers: list[str], cache, provider_chain,
    granularity: Granularity = Granularity.DAILY) -> RefreshSummary`
  - `refresh_cached(cache, provider_chain, granularity) ->
    RefreshSummary`: liest `cache.list_cached_tickers()` und
    refreshed alle
  - `refresh_universe(universe_name: str, cache, provider_chain,
    granularity) -> RefreshSummary`: nutzt PresetRepository
  - `refresh_all(cache, provider_chain, granularity, include_all: bool =
    True) -> RefreshSummary`: cached + universes
- `src/quant_trader/cache.py` (aendern): NEUE Hilfsfunktion
  `list_cached_tickers(granularity: Granularity) -> list[str]`:
  - Liest `data_dir/raw/{granularity.path_segment}/*.parquet`
  - returnt Liste ohne `.parquet`-Suffix, sortiert
- `src/quant_trader/data/cli.py` (aendern):
  - Neuer Subcommand `refresh`:
    - `python -m quant_trader.data refresh`
    - `python -m quant_trader.data refresh --tickers SPY,AGG`
    - `python -m quant_trader.data refresh --universe dax40`
  - Strukturiertes Logging pro Ticker + Summary am Ende
- `scripts/backtest_dashboard.py` (aendern):
  - Neuer Tab "Cache" (neben "Run-Form", "Read-Mode", "Vergleich")
  - ODER: Sidebar-Sektion "Cache verwalten" (siehe Hinweis unten)
  - Drei Radio-Optionen:
    1. "Alle gecachten Tickers" (default)
    2. "Universe (Dropdown: sp500, dax40, etfs)"
    3. "Ticker-Liste (Text-Input, comma-separated)"
  - Button "Refresh starten"
  - `st.progress()` fuer Progress-Anzeige (z.B. i / total)
  - `st.empty()` Container fuer Live-Log-Stream
  - Nach Abschluss: `st.dataframe()` mit RefreshSummary-Details
  - Bei Fehler: pro Ticker deutsche Fehlermeldung, andere laufen weiter
  - Strukturiertes Logging via configure_logging
  - Pragmatisch: Nutze `st.tabs([..., "Cache"])` statt Sidebar-Sektion
    (konsistenter mit US-P3.9 Pattern)
- Tests: `tests/data/test_cache_refresh.py`, `tests/data/test_refresh.py`,
  `tests/data/test_incremental.py` (NEU, gesamt mind. 15 Tests):
  - `test_cache_refresh.py` (mind. 3 Tests):
    - `test_merge_incremental_adds_new_bars`
    - `test_merge_incremental_deduplicates_overlap`
    - `test_merge_incremental_with_empty_new_bars_returns_existing`
  - `test_incremental.py` (mind. 5 Tests, mit tmp_path):
    - `test_service_get_uses_cache_when_fully_covered`
    - `test_service_get_fetches_only_missing_range`
    - `test_service_get_skips_provider_when_cache_covers`
    - `test_service_merges_incremental_into_cache`
    - `test_incremental_full_rewrite_dedup`
  - `test_refresh.py` (mind. 7 Tests, mit tmp_path + monkeypatch):
    - `test_refresh_tickers_returns_summary`
    - `test_refresh_tickers_handles_errors_per_ticker`
    - `test_refresh_cached_reads_cache_directory`
    - `test_refresh_universe_resolves_tickers`
    - `test_refresh_summary_aggregates_results`
    - `test_refresh_summary_zero_errors_when_all_ok`
    - `test_refresh_with_empty_input_returns_zero_summary`
- Doku-Updates:
  - `docs/STATE.md`: Slice 1.6 auf DONE, Tag `p1-data/1.6`
  - "Was steht"-Sektion: Inkrement-Update + Refresh-Button
  - "Was offen"-Sektion: aktualisieren
  - `docs/adr/0015-cache-refresh-architecture.md`: Status `proposed` -> `accepted`

## Out of Scope (verbindlich)

- Auto-Refresh bei Backtest-Start (Cron/Systemd/Initiator)
- Parallel-Refresh-Workers (sequentiell reicht)
- Refresh-Logs persistent (separater Log-File)
- Refresh von Intraday-Daten (Daily only in 1.6)
- Background-Worker fuer Auto-Refresh
- Cache-Lock fuer parallele Schreibprozesse
- Parquet-Partitioning nach Jahr
- Refresh-Status-Tracker (welche Tickers stale sind)

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies.
- Kein `print`, kein globaler State.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, UI-Strings deutsch (NFR-Ux-1).
- **KRITISCH**: alle 440 bestehenden Tests unveraendert gruen
- `merge_incremental` macht full rewrite der parquet-Datei (klar in
  Docstring dokumentiert), aber DEDUP erfolgt vorher
- Performance: Inkrement-Update soll fuer 100 Tickers parallel in <60s
  laufen (NFR-Perf-2 gilt pro Ticker)
- Error-Handling: pro-Ticker-Errors blockieren andere Tickers nicht

## Mapped NFRs

- NFR-Data-1 (Inkrement-Update, APPROVED - jetzt vollstaendig implementiert)
- NFR-Perf-2 (<60s fuer 5y Cache-Miss, bleibt)
- NFR-Ux-1 (deutsche UI-Texte im Dashboard)
- NFR-Obs-1 (structlog fuer Refresh-Events)

## UML-Referenz

Visualisiert in: `docs/uml/p1-data/cache-refresh.md` (Status: wird auf
APPROVED gesetzt mit diesem Slice).

## Done when

- [ ] `ParquetCache.merge_incremental(...)` + `covers_range(...)` implementiert
- [ ] `DataService.get` nutzt Inkrement-Update (kein Full-Refetch)
- [ ] `data/refresh.py` mit `refresh_tickers`, `refresh_cached`,
      `refresh_universe`, `refresh_all` + `RefreshSummary`/`RefreshResult`
- [ ] `cache.list_cached_tickers(granularity) -> list[str]`
- [ ] `data/cli.py` mit `refresh` Subcommand
- [ ] `scripts/backtest_dashboard.py` mit Cache-Tab + 3 Optionen + Progress + Summary
- [ ] Tests in `tests/data/` mit gesamt mind. 15 neuen Tests
- [ ] `make test` gruen (alle 440 alten + neuen Tests)
- [ ] `make lint` gruen
- [ ] `mypy --strict` gruen (0 errors)
- [ ] ADR-0015 auf "accepted"
- [ ] Conventional Commit `feat(p1-data): slice 1.6 cache refresh`
- [ ] `docs/STATE.md` aktualisiert: Slice 1.6 auf DONE, Tag `p1-data/1.6`

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p1-data/data-layer.md
cat docs/adr/0015-cache-refresh-architecture.md
cat docs/uml/p1-data/cache-refresh.md
cat docs/prd/p1-data/cache-refresh.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. Cron/Background-Worker sind out.
- **KRITISCH**: alle 440 bestehenden Tests unveraendert gruen.

Nach dem Coden:
- Conventional Commit mit `feat(p1-data): slice 1.6 cache refresh`.
- Commit-Body: warum merge_incremental (Dedup + Sort + Rewrite),
  warum Bulk-Refresh-Funktionen (DRY ueber CLI + Dashboard).
