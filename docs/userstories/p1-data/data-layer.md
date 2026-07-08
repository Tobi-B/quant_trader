# Phase 1 - Datenlayer: User Stories

Phase:    P1 Datenlayer
Status:   APPROVED (Story-Set am 2026-07-08)
Persona:  Tobias (privater Einsteiger-Trader)
Quelle:   Interview am 2026-07-08

Konvention: jede Story folgt INVEST + MoSCoW + T-Shirt-Size + Gherkin.
Nutzer-zentriert: das "Was & Warum", nicht das "Wie".

---

## Slice 1.1 - Universe Loader

### US-P1.1 - Standard-Listen importieren

- **Als** Trader
- **moechte ich** vorgefertigte Listen wie S&P 500, DAX 40 und ETF-Sets abrufen koennen,
- **damit** ich nicht jeden Ticker einzeln pflegen muss.

- **Priority:** Must
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** das Projekt wurde frisch aufgesetzt
  - **When** ich `python -m quant_trader.universe load --preset sp500` aufrufe
  - **Then** werden die ~500 S&P-500-Ticker geladen und in einer Datei `data/universe/sp500.csv` gespeichert
  - **And** ein Aufruf von `python -m quant_trader.universe list` zeigt sie an
  - **And** `load --preset dax40` legt die ~40 DAX-Ticker unter `data/universe/dax40.csv` an
  - **And** `load --preset etfs` legt eine kuratierte ETF-Liste (z.B. SPY, VOO, EUNL, IWDA, AGG, TLT) unter `data/universe/etfs.csv` an

- **Out of Scope:** dynamische / automatische Updates der Listen; eigene Kuration; Backtests in diesem Slice.

---

## Slice 1.2 - DataProvider + Parquet-Cache

### US-P1.2 - Historische Tagessdaten fuer eine Liste laden

- **Als** Trader
- **moechte ich** mit einem Befehl Tagessdaten fuer mehrere Ticker gleichzeitig laden koennen,
- **damit** ich schnell einen Backtest-Setup habe.

- **Priority:** Must
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** ich habe ein Universe mit Tickern geladen (Slice 1.1)
  - **When** ich `python scripts/fetch_data.py --universe sp500 --granularity daily --years 5` aufrufe
  - **Then** pro Ticker ist eine Parquet-Datei mit den letzten ~5 Jahren Tagessdaten vorhanden unter `data/raw/daily/<TICKER>.parquet`
  - **And** das Skript meldet Fortschritt ("12 / 500 fertig") und Endzeit
  - **And** bei einem API-Fehler eines Tickers wird der Lauf fuer die uebrigen Ticker fortgesetzt
  - **And** am Ende erscheint eine Zusammenfassung "ok=N, fallback=N, failed=N"

- **Out of Scope:** Intraday-Daten (eigener Slice); Daten-Validierung ueber API hinaus; Visualisierung.

### US-P1.3 - Cache schlaegt zu, kein Reload

- **Als** Trader
- **moechte ich**, dass ein zweiter Aufruf mit denselben Daten den Cache nutzt und keine API-Aufrufe macht,
- **damit** mein API-Kontingent geschont wird.

- **Priority:** Must
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** `data/raw/daily/SPY.parquet` enthaelt bereits Bars von 2020-01-01 bis 2024-12-31
  - **When** ich `python scripts/fetch_data.py SPY --start 2020-01-01 --end 2024-12-31` aufrufe
  - **Then** wird **kein** externer API-Call gemacht (Logger meldet `cache.hit`)
  - **And** die Daten werden in unter 1 Sekunde zurueckgegeben
  - **And** bei wiederholtem Aufruf ist die Dauer stabil (< 1 s)

- **Out of Scope:** automatische Refresh-Erkennung ("neue Tage seit gestern"); partielle Updates.

### US-P1.4 - Automatischer Fallback bei Provider-Fehler

- **Als** Trader
- **moechte ich**, dass bei Ausfall eines Providers automatisch der andere genutzt wird,
- **damit** mein Daten-Run nie blockiert.

- **Priority:** Should
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** Alpha Vantage antwortet mit Rate-Limit (HTTP 429) oder 5xx
  - **When** ich einen Fetch starte
  - **Then** wird automatisch yfinance als Fallback verwendet
  - **And** der Logger meldet `provider.fallback` mit Begruendung (z.B. `alpha_vantage.rate_limited`)
  - **And** der Datensatz wird trotzdem geschrieben
  - **And** wenn beide Provider scheitern: klare Fehlermeldung `data.unavailable` mit Hinweis auf Universe-Liste

- **Out of Scope:** konfigurierbare Provider-Reihenfolge (immer Alpha Vantage zuerst); Retry-Tuning (kommt in PRD).

### US-P1.6 - Klare Fehlermeldung bei ungueltigem Ticker

- **Als** Trader
- **moechte ich** eine klare Fehlermeldung bekommen, wenn ich einen nicht-existierenden Ticker eingebe,
- **damit** ich den Fehler schnell korrigieren kann.

- **Priority:** Should
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** ich gebe einen Ticker ein, der weder bei Alpha Vantage noch bei yfinance existiert
  - **When** ich `python scripts/fetch_data.py ZZZZZ --start 2023-01-01 --end 2023-12-31` aufrufe
  - **Then** erscheint eine Fehlermeldung `ticker.not_found: ZZZZZ` mit Hinweis auf Universe-Liste
  - **And** es wird **keine** Cache-Datei geschrieben
  - **And** der Exit-Code ist ungleich 0
  - **And** der Lauf bricht ab (kein weiterer Ticker wird versucht, falls Multi-Ticker-Modus)

- **Out of Scope:** Ticker-Vorschlaege ("meintest du AAPL?"); Bulk-Validierung.

---

## Slice 1.3 - Intraday-Support

### US-P1.5 - Intraday-Daten (Stunden oder Minuten) optional laden

- **Als** Trader
- **moechte ich** Intraday-Daten (z.B. Stunden- oder 15-Minuten-Bars) optional laden koennen,
- **damit** ich auch kuerzere Strategien testen kann.

- **Priority:** Could
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** ich habe bereits Tagessdaten fuer AAPL
  - **When** ich `python scripts/fetch_data.py AAPL --granularity 60m --years 1` aufrufe
  - **Then** werden Stundenbars der letzten ~252 Handelstage geladen
  - **And** die Daten landen unter `data/raw/60m/AAPL.parquet` (separater Pfad, nicht `daily/`)
  - **And** der Logger gibt eine Warnung `intraday.api_quota_high` aus
  - **And** der Cache-Mechanismus (US-P1.3) funktioniert genauso fuer Intraday-Dateien

- **Out of Scope:** Realtime-Streaming; Tick-Daten; Multi-Source-Aggregation.

---

## Mapped NFRs (siehe docs/requirements/nfrs.md)

| Story  | NFR-IDs                                       |
|--------|------------------------------------------------|
| US-P1.1 | NFR-Sec-1 (keine Secrets in Listen)            |
| US-P1.2 | NFR-Perf-2, NFR-Data-1, NFR-Obs-1              |
| US-P1.3 | NFR-Rel-1, NFR-Data-1, NFR-Perf-2              |
| US-P1.4 | NFR-Rel-1, NFR-Obs-1                           |
| US-P1.5 | NFR-Perf-2, NFR-Data-1                         |
| US-P1.6 | NFR-Ux-1                                      |

---

## Definition of Done (alle Stories)

- [ ] Implementierung gemaess Scope der jeweiligen Story.
- [ ] Gherkin-Akzeptanzkriterien sind in `tests/` als pytest-Tests umgesetzt.
- [ ] `make lint`, `make test`, `make smoke` gruen.
- [ ] Conventional Commits, einer pro Story (oder pro sinnvollem Sub-Schritt).
- [ ] `docs/STATE.md` und ggf. `docs/prd/p1-data/<slice>.md` aktualisiert.
- [ ] UML-Diagramm(e) fuer den jeweiligen Slice sind APPROVED (Structure + Flow + Sequence).