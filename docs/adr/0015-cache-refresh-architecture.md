# ADR 0015: Data Cache Refresh-Architektur (Bulk + Inkrementell + UI)

Status:     accepted
Datum:      2026-07-15
Phase:      P1 Datenlayer (Erweiterung)
Supersedes: -
Superseded by: -

## Context

Der User hat zwei neue Anforderungen:

1. **Bulk Cache Refresh**: Aktuell muss er fuer jeden Ticker einzeln
   `python -m quant_trader.data TICKER` aufrufen. Schmerzhaft bei
   vielen Tickers (z.B. Universe dax40 = 40 Calls). Erwuenscht: ein
   Button der mehrere Tickers auf einmal laedt.

2. **Immer aktuelle Daten**: Der Cache ist manchmal stale. Erwuenscht:
   Auto-Refresh-Logik, die nur die fehlenden/neuen Bars laedt
   (Inkrement-Update statt Full-Refetch, NFR-Data-1 ist bereits
   APPROVED aber nicht vollstaendig implementiert).

Im Repo vorhanden:
- `data/cache.py` mit `ParquetCache(base_dir)`, `read()`, `write()`
  - ABER: `write()` macht aktuell full rewrite (`df.to_parquet(path)`)
    statt echten Inkrement-Update
- `data/refresh.py` existiert NICHT
- `scripts/backtest_dashboard.py` hat eine "Run-Form" + "Read-Mode" +
  "Vergleich" Sektion; KEIN Cache-Management-Tab
- `universe/presets.py` mit `PresetRepository.all()` (Liste der
  Tickers in einem Universe)
- 440 Tests gruen

## Decision

### 1. Inkrement-Update (US-P1.8) - nfr-data-1

**Architektur**:
- Neue Methode `ParquetCache.merge_incremental(ticker, granularity, new_bars) -> Path`
  - Liest existierenden Cache (falls vorhanden)
  - Konkateniert `existing_bars + new_bars`
  - Dedup via `(timestamp, ticker)` Index
  - Sortiert nach `timestamp` asc
  - Schreibt zurueck mit `df.to_parquet(path, index=False)`
- `ParquetCache.fetch_incremental(ticker, granularity, start, end, provider_chain)`:
  - Berechnet `existing_range = (min_date, max_date)` aus Cache
  - Berechnet `missing_ranges` (alles ausser existing_range)
  - Falls `missing_ranges` leer: Cache-Coverage, kein Fetch noetig
  - Sonst: Fetch via Provider-Chain, merge_incremental
- `DataService.get` nutzt `fetch_incremental` statt `provider_chain.fetch`

### 2. Bulk-Refresh-Funktionen (US-P1.9)

`data/refresh.py` (NEU, ~80 Zeilen) mit:

```python
def refresh_cached(data_dir: Path, provider_chain, granularity) -> RefreshSummary
def refresh_universe(universe_name: str, data_dir, provider_chain, granularity) -> RefreshSummary
def refresh_tickers(tickers: list[str], data_dir, provider_chain, granularity) -> RefreshSummary
def refresh_all(data_dir, provider_chain, granularity) -> RefreshSummary  # cached + universes optional
```

`RefreshSummary` (frozen dataclass):
- `total: int`, `updated: int`, `unchanged: int`, `errors: int`,
  `duration_seconds: float`, `details: list[RefreshResult]`

`RefreshResult` (frozen dataclass):
- `ticker: str`, `status: Literal["updated", "unchanged", "error"]`,
  `bars_added: int`, `error_message: str | None`, `duration_seconds: float`

Alle nutzen `ParquetCache.merge_incremental` (NFR-Data-1).

### 3. CLI-Integration

`data/cli.py` (aendern):
- Neuer Subcommand `refresh`:
  - `python -m quant_trader.data refresh` (alle gecachten)
  - `python -m quant_trader.data refresh --tickers SPY,AGG,GLD`
  - `python -m quant_trader.data refresh --universe dax40`
- Strukturiertes Logging: `data.refresh.start`, `data.refresh.ticker`,
  `data.refresh.complete`

### 4. Streamlit Dashboard Cache-Management-Tab (US-P1.9)

`scripts/backtest_dashboard.py` (aendern):
- Neuer Tab "Cache" mit Sidebar-Sektion "Cache verwalten"
- Drei Radio-Optionen:
  - "Alle gecachten Tickers" (default)
  - "Universe" (Dropdown aus PresetRepository.all())
  - "Ticker-Liste" (Text-Input, comma-separated)
- Button "Refresh starten"
- `st.progress()` fuer Progress-Anzeige
- `st.empty()` fuer Live-Log-Stream
- `st.dataframe()` fuer RefreshSummary-Ergebnisse
- Errors werden pro Ticker angezeigt, andere Tickers laufen weiter

### 5. Cache-Performance

- Inkrement-Update reduziert API-Calls drastisch:
  - Erster Fetch SPY (5y) = ~1270 Bars = 1 API-Call
  - Tagesupdate SPY = ~1 Bar (oder 0 falls Wochenende) = 1 API-Call
  - Statt full re-fetch von 1270 Bars
- FMP Free-Tier (250 calls/Tag) reicht fuer ~250 Tickers pro Tag

## Consequences

**Positiv**
- Bulk-Refresh spart hunderte manuelle CLI-Aufrufe
- Inkrementelles Update schont FMP-Quota (NFR-Data-1 vollstaendig erfuellt)
- Dashboard-UI macht Refresh sichtbar (Live-Progress, Errors)
- Backward-Compat: `provider.fetch()` und `cache.write()` bleiben
  unveraendert (Add-On oben drauf)
- 440 bestehende Tests unveraendert gruen

**Negativ**
- Inkrement-Update hat Race-Condition-Risiko wenn parallel Fetch-
  Prozesse laufen (akzeptabel fuer persoenlichen Use-Case, ein User)
- Streamlit-UI hat keinen Background-Worker: Refresh blockiert UI
  (akzeptabel, da FMP schnell ist)
- Refresh-Logs nicht persistent (nur structlog in stderr)

**Neutral**
- `merge_incremental` ist eine neue Cache-Methode, kein Ersatz
- Universe-Liste hat aktuell 3 presets (sp500, dax40, etfs) - reicht
- Refresh-Funktionen sind synchron (kein asyncio) - reicht fuer
  persoenlichen Use-Case

## Alternatives Considered

- **Background-Worker fuer Refresh**: abgelehnt, Komplexitaet vs.
  Nutzen unausgewogen
- **Auto-Refresh bei jedem Backtest-Start**: abgelehnt, der User kann
  explizit ueber Dashboard refreshen
- **Cron/Systemd fuer taeglichen Refresh**: out-of-scope, User
  kann selbst cron einrichten falls erwuenscht
- **Refresh auf Intraday-Granularitaeten**: out-of-scope fuer Slice 1.6
  (Daily-only, Intraday kommt spaeter)
- **Cache-Lock fuer parallele Writes**: abgelehnt, Single-User-
  Use-Case
- **Parquet-Partitioning nach Jahr**: out-of-scope, aktuelle
  Granularitaet (daily) reicht

## References

- `src/quant_trader/data/cache.py` (aendern: merge_incremental)
- `src/quant_trader/data/service.py` (aendern: nutzt fetch_incremental)
- `src/quant_trader/data/refresh.py` (NEU)
- `src/quant_trader/data/cli.py` (aendern: refresh subcommand)
- `scripts/backtest_dashboard.py` (aendern: Cache-Tab)
- `docs/userstories/p1-data/data-layer.md` (US-P1.8, US-P1.9)
- `docs/prd/p1-data/cache-refresh.md` (Slice-PRD)
- `docs/uml/p1-data/cache-refresh.md` (Mermaid)
- NFR-Data-1 (Inkrement-Update, APPROVED)
- NFR-Perf-2 (<60s fuer 5y Cache-Miss)
- NFR-Ux-1 (deutsche UI-Texte)
- NFR-Obs-1 (structlog)
- ADR-0009 (FMP als Primary, bleibt unveraendert)
