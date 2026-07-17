# ADR 0017: Company Search via FMP + Service-Layer

Status:     accepted
Datum:      2026-07-17
Phase:      P3 Backtest-Engine + Reports (Erweiterung)
Supersedes: -
Superseded by: -

## Context

Das Streamlit-Dashboard (Slices 3.3 + 3.5 + 3.6) ermoeglicht das Starten von
Backtests im Custom-Ticker-Modus. Der Trader muss dazu den exakten Ticker
kennen (z.B. `AAPL`). Viele Einsteiger kennen aber nur den Unternehmensnamen
("Apple"), das Ticker-Kuerzel ist nicht offensichtlich.

Phase 1 hat Financial Modelling Prep (FMP) als Primary-Provider etabliert
(NFR-Data-3, ADR-0009). FMP bietet einen Search-Endpoint
`GET /api/v3/search?query=...&limit=...&exchange=...&apikey=...`, der genau
fuer diesen Use-Case gedacht ist.

Im Repo vorhanden:
- `src/quant_trader/data/financial_modelling_prep.py` mit `FinancialModellingPrepProvider`
  fuer historische Bars (Daily, 60m, 15m)
- `src/quant_trader/core/types.py` mit `Bar`, `Granularity`, `Preset`
- `src/quant_trader/core/errors.py` mit `DataError`-Hierarchie
- `src/quant_trader/data/factory.py` mit `build_chain(settings)` (Fallback-Kette)
- `scripts/backtest_dashboard.py` mit `DashboardRunner`, Tabs "Run-Form",
  "Read-Mode", "Vergleich", "Cache", "Strategien"
- 505 Tests gruen (vor diesem Slice)

## Decision

### 1. FMP als Search-Provider

`FinancialModellingPrepProvider` (in `src/quant_trader/data/financial_modelling_prep.py`)
bekommt eine neue Public-Methode `search(query, *, limit=20, exchange=None) -> list[Instrument]`.
Begruendung:
- FMP ist bereits Primary-Provider fuer Marktdaten (NFR-Data-3)
- Endpoint ist Free-Tier-kompatibel (gleicher Key wie fuer historische Daten)
- Reduziert die Anzahl der API-Keys und Provider-Configs
- Der Provider-Code folgt dem bestehenden Muster (URL-Build via `urlencode`,
  HTTP-200/429/Error-Handling, `ProviderError`/`RateLimitedError`)

Der Endpoint wird **nicht** in die Fallback-Kette (`build_chain`) aufgenommen,
weil:
- Search ist ein UI-Helper, kein Pflicht-Datenpfad (Trader kann Ticker manuell eingeben)
- Free-Tier-Limits wuerden durch mehrfache Provider-Calls schneller erschoepft
- Fallback-Kette ist auf historische Bars optimiert (rate-limit-freundlich)

### 2. `Instrument` und `SearchUnavailableError` im Core

- `Instrument(ticker, name, exchange, currency)` als frozen dataclass in
  `core/types.py`. Bewusst **nicht** im Data-Layer, weil:
  - der Typ auch von der UI konsumiert wird
  - keine I/O-Abhaengigkeit
  - einfach testbar
- `SearchUnavailableError(DataError)` mit `query` und `reason` in
  `core/errors.py`. Mapping erfolgt im Service-Layer (siehe 3.).

### 3. `CompanySearchService` als Service-Layer

`src/quant_trader/data/instrument_search.py` (NEU) enthaelt:
- `InstrumentSearchProvider` Protocol: `search(query, *, limit, exchange) -> list[Instrument]`
- `CompanySearchService(provider)` mit `search(query, *, limit=20) -> list[Instrument]`:
  - `query.strip()` leer -> `[]` (kein Provider-Call)
  - `limit` auf `[1, 100]` gebounded
  - Strukturiertes Logging `instrument.search.start` / `.complete` / `.unavailable`
  - Faengt `DataError` aus Provider ab und wirft `SearchUnavailableError(query, reason)`

Begruendung:
- Trennt Streamlit-UI von der FMP-API (testbar ohne Streamlit)
- Konsistentes Error-Handling: Dashboard faengt nur `SearchUnavailableError` ab
- Logging im Service, nicht in der UI (NFR-Obs-1)
- Protocol erlaubt spaeter einen alternativen Provider (Mock fuer Tests,
  potenziell OpenFIGI als Fallback - out-of-scope jetzt)

### 4. Dashboard-Integration

`scripts/backtest_dashboard.py`:
- `CompanySearchService` wird in `_build_services()` ueber `@st.cache_resource`
  einmal pro Streamlit-Session gebaut
- Neuer Helper `_render_instrument_search(search_service)`:
  - `st.text_input` fuer Query
  - `st.button("Unternehmen suchen")` (disabled bei leerer Query)
  - `st.selectbox` mit Label-Formatter `<name> - <ticker> (<exchange>)`
  - "Auswahl übernehmen" Button -> `st.session_state["run_ticker"] = result.ticker` + `st.rerun()`
  - Fehlerfall: `st.error("Die Unternehmenssuche ist vorübergehend nicht verfügbar. ...")`
  - Keine Treffer: `st.info("Keine Treffer für '<q>'. Bitte Suchbegriff ändern.")`
- `_render_run_form` ruft `_render_instrument_search` **nur** wenn
  `universe_choice == "(Custom-Ticker)"` (US-P3.11 AC: Universe-Preset-Modus
  benoetigt keine Suche)

### 5. Rate-Limit-Strategie

FMP Free-Tier hat 250 Calls/Tag (NFR-Data-3). Search ist ein UI-Helper, daher:
- Kein automatisches Pre-Fetching (Suche nur on-demand per Klick)
- Kein Caching der Treffer (jede Suche ist ein neuer HTTP-Call)
- `RateLimitedError` (HTTP 429) wird zu `SearchUnavailableError` gemappt,
  Dashboard zeigt deutsche Meldung und Trader kann Ticker manuell eingeben
- Free-Tier ist akzeptabel fuer persoenlichen Use-Case

## Consequences

**Positiv**
- Einsteiger koennen Backtests ohne Tickerkenntnis starten (US-P3.11 erfuellt)
- Klare Schicht-Trennung: Provider (FMP) -> Service (CompanySearchService) -> UI (Dashboard)
- `Instrument` und `SearchUnavailableError` im Core sind ohne Streamlit testbar
- Strukturiertes Logging im Service (NFR-Obs-1) ohne UI-Coupling
- Backward-Compat: 505 bestehende Tests unveraendert gruen
- `DashboardRunner` und `BacktestOrchestrator` unveraendert (NFR-Data-1)

**Negativ**
- FMP Free-Tier (250 Calls/Tag) wird mit Such-Calls geteilt (bisher nur Bar-Fetches)
- Kein Caching der Treffer (gleicher Query = neuer HTTP-Call)
- FMP-Fehlerton "Error Message" im JSON-Response wird im Search-Endpoint als
  `invalid JSON response` interpretiert (kein Ticker-Not-Found-Pfad noetig)
- Suchergebnisse nur auf englisch (FMP liefert keine Lokalisierung)

**Neutral**
- Protocol `InstrumentSearchProvider` ist Praktikabilitaet fuer Mock-Tests;
  ein zweiter Provider ist nicht geplant
- `Instrument` hat keine `isin`/`sector`/`country` - koennte spaeter ergaenzt
  werden, falls Universe-Filter gebraucht werden (MoSCoW: Could)

## Alternatives Considered

- **OpenFIGI / AlphaVantage Search als zusaetzlicher Provider**: abgelehnt,
  Free-Tier-Limits wuerden verwaltet, mehr Config, YAGNI fuer persoenlichen
  Use-Case. Protocol ermoeglicht spaeteren Tausch.
- **Search im `build_chain`-Fallback einhaengen**: abgelehnt, weil Search
  ein UI-Helper ist und keine Fallback-Semantik braucht (Trader kann
  Ticker manuell eingeben).
- **Caching der Treffer (z.B. 1 Stunde)**: abgelehnt, Free-Tier reicht,
  komplexere Invalidierung noetig, YAGNI.
- **Search-Results direkt im Dashboard cachen (st.session_state)**: implementiert
  mit minimaler Logik (Query + Results), damit `st.rerun()` nach "Auswahl
  übernehmen" den State zuruecksetzt.
- **Provider-Call via `requests.Session` aus dem Dashboard**: abgelehnt,
  Layer-Trennung wuerde verletzt, schwer testbar.
- **Async-Suche mit `asyncio` + `httpx`**: abgelehnt, Streamlit ist sync,
  Search ist sub-second, Overhead nicht gerechtfertigt.
- **Search nach ISIN / WKN**: out-of-scope, FMP-Free-Tier liefert keine
  europaeischen Identifier, manuelle Eingabe reicht.

## References

- `src/quant_trader/core/types.py` (Instrument, NEU)
- `src/quant_trader/core/errors.py` (SearchUnavailableError, NEU)
- `src/quant_trader/data/financial_modelling_prep.py` (search-Methode, NEU)
- `src/quant_trader/data/instrument_search.py` (NEU)
- `scripts/backtest_dashboard.py` (`_render_instrument_search`, eingebunden in Run-Form)
- `tests/data/test_instrument_search.py` (NEU)
- `tests/test_dashboard_company_search.py` (NEU)
- `docs/userstories/p3-backtest/company-search.md` (US-P3.11)
- `docs/uml/p3-backtest/company-search.md` (APPROVED)
- `docs/prd/p3-backtest/company-search.md` (Slice-PRD)
- NFR-Ux-1 (deutsche UI-Texte)
- NFR-Data-1 (Cache-Pfad bleibt unveraendert)
- NFR-Data-3 (FMP ist Primary Provider, Free-Tier)
- NFR-Sec-1 (API-Key via env)
- NFR-Obs-1 (structlog)
- ADR-0009 (FMP als Primary Provider)