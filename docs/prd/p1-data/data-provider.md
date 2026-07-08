# PRD: Slice 1.2 - DataProvider + Cache

Phase:    P1 Datenlayer
Slice:    1.2 DataProvider + Cache
Status:   APPROVED  (2026-07-08, Stories + Diagram)
Author:   opencode
Created:  2026-07-08
Updated:  2026-07-08

## Goal

Multi-Ticker-Daten aus Primaer-Provider (Alpha Vantage) mit automatischem
Fallback auf yfinance laden, lokal in Parquet cachen, und ueber eine
einheitliche CLI verfuegbar machen. Cache-Hits machen keinen API-Call.

## Scope (IN)

- `DataProvider` Protocol mit `fetch(ticker, start, end, granularity) -> list[Bar]`.
- `YFinanceProvider` (Free, ohne Key).
- `AlphaVantageProvider` (mit API-Key aus env, ohne Key = ProviderError).
- `FallbackProvider` als Decorator: probiert Provider-Kette, gibt
  `DataUnavailable` zurueck, wenn alle scheitern; `TickerNotFound` sofort.
- `ProviderFactory.build_chain(settings)` baut die Kette aus Settings.
- `ParquetCache` mit `read`, `write`, `covers` (Range-Check).
- `DataService` orchestriert Cache-Check + Provider-Fetch + Cache-Write.
- `fetch_data` CLI (Single- und Multi-Ticker via `--universe`).
- Strukturierte Logs (structlog), deutsche Fehlermeldungen (stderr).

## Out of Scope (verbindlich)

- Inkrementelle Cache-Updates (Cache-Miss = komplettes Refetch + Replace).
- Realtime/Intraday > 60min (Slice 1.3 fuehrt 60m ein; 15m spaeter).
- Parallel-Loader (sequentiell; Multi-Ticker spaeter).
- Provider-agnostische Schema-Migration (Schema ist fix: timestamp/O/H/L/C/AC/V).
- Alpha Vantage Intraday-Funktion (TIME_SERIES_INTRADAY) - kommt mit Slice 1.3.
- Ticker-Vorschlaege bei Fehler.
- Bulk-Validierung vor Fetch.

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies ausserhalb `pyproject.toml` (alle vorhanden: pandas,
  pyarrow, requests, yfinance, pydantic).
- Kein `print`, kein globaler State.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, CLI-Strings deutsch, Logs englisch.

## Mapped NFRs

- NFR-Rel-1 (Daten-Fetch idempotent): Cache-Hit-Pfad in DataService.
- NFR-Perf-2 (5 Jahre < 60s): sequentieller Single-Ticker-Loop; YFinance typischerweise <10s.
- NFR-Data-1 (Parquet-Cache mit Inkrement - hier als einfaches Cache-Hit umgesetzt):
  Hinweis: kein echtes Inkrement-Update in 1.2 (out of scope), aber Cache-Pfad ist
  deterministisch.
- NFR-Obs-1 (structlog): jeder Provider-Call und Cache-Hit wird geloggt.
- NFR-Ux-1 (deutsche CLI, klare Fehler): deutsche stderr-Texte, JSON-Logs auf stdout.
- NFR-Sec-1 (Keys via .env): Alpha Vantage Key nur via `ALPHAVANTAGE_KEY` env.

## UML-Referenz

Visualisiert in: `docs/uml/p1-data/data-provider.md`

## Done when

- [ ] Alle Klassen implementiert gem. Diagramm (DataProvider, AlphaVantageProvider,
      YFinanceProvider, FallbackProvider, ProviderFactory, ParquetCache, DataService,
      FetchDataCLI).
- [ ] Error-Hierarchie: DataError, ProviderError, RateLimitedError, TickerNotFound,
      DataUnavailable.
- [ ] Tests: error-Hierarchie, jeder Provider (mit Mock fuer AV), Fallback-Decorator,
      Cache (read/write/covers), DataService (Cache-Hit-Pfad, Provider-Pfad,
      TickerNotFound-Pfad), CLI (Erfolg, TickerNotFound exit 1).
- [ ] `make lint` gruen, `make test` gruen, `uv run python -m quant_trader.data --help` laeuft.
- [ ] Smoke-Test mit echtem Ticker (z.B. SPY, ein Tag) liefert Parquet-Datei.
- [ ] `docs/STATE.md` aktualisiert, Tag `p1-data` gesetzt.