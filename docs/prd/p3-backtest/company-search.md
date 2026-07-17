# PRD: Slice 3.7 - Unternehmens- und Ticker-Suche im Dashboard

Phase:    P3 Backtest-Engine + Reports
Slice:    3.7 Unternehmens- und Ticker-Suche im Dashboard
Story:    US-P3.11 (siehe docs/userstories/p3-backtest/company-search.md)
Status:   APPROVED (User-Story + UML bereits APPROVED)
Author:   opencode
Created:  2026-07-17
Updated:  2026-07-17

## Goal

Das Streamlit-Dashboard (Slices 3.3 + 3.5 + 3.6 + 1.6 + 2.6) im Custom-Ticker-Modus
des Run-Forms um eine Unternehmens- und Ticker-Suche erweitern. Ein Trader, der
das Boersenkuerzel eines Unternehmens nicht kennt, soll den Namen (oder einen
Teil davon) eingeben koennen und aus der Trefferliste das gewuenschte Instrument
auswaehlen. Die Auswahl uebernimmt den Ticker in das bestehende Backtest-Formular;
Backtest-Orchestrator und Cache-Pfad bleiben unveraendert.

## Scope (IN)

- `src/quant_trader/core/types.py` (ERWEITERN):
  - `Instrument` (NEU, frozen dataclass) mit Feldern
    `ticker: str`, `name: str`, `exchange: str`, `currency: str`
- `src/quant_trader/core/errors.py` (ERWEITERN):
  - `SearchUnavailableError(DataError)` mit `query: str`, `reason: str`
- `src/quant_trader/data/financial_modelling_prep.py` (ERWEITERN):
  - `FinancialModellingPrepProvider.search(query, *, limit=20, exchange=None) -> list[Instrument]`
    - Endpoint `GET /api/v3/search?query=...&limit=...&exchange=...&apikey=...`
    - `limit` wird auf `[1, 100]` gebounded
    - Leere `query.strip()` -> leere Liste (kein HTTP-Call)
    - HTTP 200 + Liste -> `_parse_search_results` (Symbol uppercase, Name trimmed,
      Exchange aus `stockExchange`/`exchangeShortName`/`exchange`, Currency aus
      `currency`; Zeilen ohne Symbol/Name werden uebersprungen)
    - HTTP 200 + Dict -> `ProviderError("invalid JSON response")`
    - HTTP 200 + kein JSON-Array -> `ProviderError("invalid JSON response")`
    - HTTP 429 -> `RateLimitedError`
    - HTTP != 200/429 -> `ProviderError`
    - Network-Error -> `ProviderError`
    - API-Key fehlt -> `ProviderError("FINANCIAL_MODELLING_PREP_KEY not set")`
- `src/quant_trader/data/instrument_search.py` (NEU):
  - `InstrumentSearchProvider` Protocol (search(query, *, limit, exchange))
  - `CompanySearchService(provider)` mit `search(query, *, limit=20) -> list[Instrument]`:
    - leerer `query.strip()` -> `[]` (kein Provider-Call)
    - `limit` auf `[1, 100]` gebounded
    - Strukturiertes Logging `instrument.search.start` (query, limit),
      `instrument.search.complete` (query, count),
      `instrument.search.unavailable` (query, error_type) bei `DataError`
    - Faengt `DataError` aus Provider ab und wirft `SearchUnavailableError(query, reason)`
      (Dashboard bekommt so eine klare Ausnahme ohne Provider-Details)
- `scripts/backtest_dashboard.py` (ERWEITERN):
  - `CompanySearchService` wird in `_build_services()` einmalig gebaut
    (via `@st.cache_resource`) mit `FinancialModellingPrepProvider(api_key=settings.fmp_api_key)`
  - Neuer Helper `_render_instrument_search(search_service: CompanySearchService)`:
    - Caption "Unternehmen oder ETF suchen, wenn der Ticker unbekannt ist."
    - `st.text_input("Unternehmensname oder Ticker", key="instrument_search_query", placeholder="z.B. Apple oder AAPL")`
    - Button "Unternehmen suchen" (disabled bei leerer Query)
    - Bei Klick: `search_service.search(query)`; `SearchUnavailableError` -> deutsche
      Fehlermeldung ueber `st.error("Die Unternehmenssuche ist vorübergehend nicht
      verfügbar. Du kannst den Ticker unten manuell eingeben.")`
    - Trefferanzeige in `st.selectbox("Suchtreffer auswählen")` mit Label
      `"<name> - <ticker> (<exchange>)"`
    - Button "Auswahl übernehmen" -> `st.session_state["run_ticker"] = result.ticker`
      und `st.rerun()`
    - Keine Treffer -> `st.info("Keine Treffer für '<q>'. Bitte Suchbegriff ändern.")`
  - `_render_run_form(...)` ruft `_render_instrument_search` NUR wenn
    `universe_choice == _CUSTOM_TICKER_OPTION`
- Tests:
  - `tests/data/test_instrument_search.py` (NEU, mind. 10 Tests):
    - `search()` parst Liste mit `symbol`, `name`, `stockExchange`, `currency`
      zu `Instrument(symbol_upper, name, exchange, currency)`
    - `search()` ueberspringt Zeilen ohne `symbol`/`name`
    - `search()` encoded Query (Leerzeichen -> `+`) und boundet `limit`
    - `search()` liefert `[]` fuer leere Query ohne HTTP-Call
    - `search()` wirft `RateLimitedError` bei HTTP 429
    - `search()` wirft `ProviderError` bei ungueltigem Payload (Dict statt Liste)
    - `search()` wirft `ProviderError` wenn API-Key fehlt
    - `CompanySearchService.search()` trimmed Query, bounded `limit`, gibt Provider-Result zurueck
    - `CompanySearchService.search()` ruft Provider NICHT bei leerer Query
    - `CompanySearchService.search()` mappt `DataError` -> `SearchUnavailableError`
      mit `query` und `reason`
    - `CompanySearchService.search()` propagiert leere Treffer ohne Fehler
  - `tests/test_dashboard_company_search.py` (NEU, ~4 Source-Inspection-Tests):
    - Dashboard importiert `CompanySearchService` und `FinancialModellingPrepProvider`
    - Dashboard ruft `_render_instrument_search(search_service)` mit dem richtigen
      Argument-Namen
    - Dashboard nutzt `_TICKER_KEY = "run_ticker"` und gibt Ticker an Runner weiter
    - Dashboard faengt `SearchUnavailableError` ab und zeigt die deutsche Fehlermeldung

## Out of Scope (verbindlich)

- Neue Such-Provider (z.B. AlphaVantage-Search, OpenFIGI) - FMP reicht fuer
  Free-Tier + ist bereits Primary Provider (NFR-Data-3)
- Filter nach Land/Boersenplatz in der UI (MoSCoW: Could)
- Orderaufgabe, automatische Treffer-Auswahl ohne Nutzerbestaetigung (Won't)
- Suche auch im Universe-Preset-Modus (US-P3.11 AC: nicht erforderlich)
- Universelle Suche (z.B. Suche nach Strategien, Reports) - Fokus auf Ticker
- Eigener Suchdienst / Cache fuer Suchergebnisse (FMP liefert live)
- Internationale Namen / Lokalisierung (Suche uebergibt Query 1:1 an FMP,
  Free-Tier liefert englische Bezeichnungen)
- Async-Suche (UI ist ohnehin single-threaded)
- Aenderungen am BacktestOrchestrator / DashboardRunner / Cache

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies (requests ist bereits da).
- Kein `print`, kein globaler State ausserhalb `st.session_state`.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, UI-Strings deutsch (NFR-Ux-1).
- Logs englisch, snake_case.action-Convention (NFR-Obs-1).
- API-Key kommt ausschliesslich aus `settings.fmp_api_key` (NFR-Sec-1).
- `Instrument` und `SearchUnavailableError` leben in `core/`, damit sie
  auch ohne Streamlit-Import testbar sind.
- `CompanySearchService` ist pure-Logik ohne Streamlit, vollstaendig testbar.
- FMP-Fehler werden im Service-Layer in `SearchUnavailableError` gemappt,
  damit das Dashboard nur einen einzigen Exception-Typ abfangen muss.

## Mapped NFRs

- NFR-Ux-1: Deutsche UI-Texte und klare, actionable Fehlermeldungen
  (Caption "Unternehmen oder ETF suchen ...", "Keine Treffer für '<q>' ...",
   "Die Unternehmenssuche ist vorübergehend nicht verfügbar ...").
- NFR-Data-1: Die gewaehlte Instrument-Auswahl gibt nur den Ticker an den
  bestehenden `DashboardRunner` weiter; Backtest-Orchestrator und Cachepfad
  bleiben unveraendert.
- NFR-Sec-1: API-Key kommt aus `settings.fmp_api_key` (env-gestuetzt), kein
  Hartcoding im Code.
- NFR-Obs-1: Strukturiertes Logging (`instrument.search.start` /
  `.complete` / `.unavailable`).

## UML-Referenz

Visualisiert in: `docs/uml/p3-backtest/company-search.md` (Status: APPROVED).
Drei Diagramme: Structure (Class), Flow (Activity), Sequence.

## Done when

- [x] User-Story `US-P3.11` APPROVED in `docs/userstories/p3-backtest/company-search.md`.
- [x] UML `docs/uml/p3-backtest/company-search.md` Status APPROVED mit drei Mermaid-Diagrammen.
- [x] `Instrument` in `core/types.py`, `SearchUnavailableError` in `core/errors.py`.
- [x] `FinancialModellingPrepProvider.search(...)` implementiert mit FMP-Endpoint
      `/api/v3/search` und Parser.
- [x] `CompanySearchService` in `data/instrument_search.py` mit Logging und
      `DataError -> SearchUnavailableError` Mapping.
- [x] `_render_instrument_search` in `scripts/backtest_dashboard.py`, eingebunden
      nur im Custom-Ticker-Modus des Run-Forms.
- [x] Tests in `tests/data/test_instrument_search.py` und
      `tests/test_dashboard_company_search.py`.
- [x] `uv run pytest -m "not live and not slow"` gruen (519 Tests).
- [x] `uv run ruff check` + `uv run ruff format --check` gruen.
- [x] `uv run mypy --strict src` gruen.
- [x] Streamlit-Dashboard Modul-Load OK (manuell smoke via `importlib.util`).
- [x] Conventional Commit(s):
      - `docs(p3-backtest): approve slice 3.7 company-search design` (UML DRAFT -> APPROVED)
      - `feat(p3-backtest): slice 3.7 company-search via FMP` (Implementation + Tests)
- [x] ADR-0017 akzeptiert (FMP als Search-Provider, Service-Layer-Pattern).
- [x] `docs/STATE.md` aktualisiert: Slice 3.7 DONE, Tag `p3-backtest/3.7`.

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p3-backtest/company-search.md
cat docs/uml/p3-backtest/company-search.md
cat docs/prd/p3-backtest/company-search.md   # diese Datei
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht.
- Neue Provider (AlphaVantage-Search, OpenFIGI) -> out-of-scope.
- Aenderungen am BacktestOrchestrator -> out-of-scope (NFR-Data-1).

Nach dem Coden:
- Conventional Commits: erst DRAFT -> APPROVED UML, dann Implementation.
- Commit-Body: warum FMP als Search-Provider (NFR-Data-3), warum Service-Layer
  (testbar ohne Streamlit), was verworfen wurde (z.B. Inline-Search im
  Dashboard ohne `CompanySearchService`).