# PRD: Slice 1.5 - Financial Modelling Prep (FMP) Provider

Phase:    P1 Datenlayer
Slice:    1.5 FMP-Provider (Free-Tier, daily + intraday)
Status:   DRAFT  (User "Haupt API = FMP" gilt als implizite Approval; UML auf APPROVED setzen)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Financial Modelling Prep (FMP) als Primary Provider in die bestehende
Provider-Chain einbinden, sodass Backtests und Universe-Loads standard-
maessig FMP nutzen. Free-Tier (250 calls/Tag) ist ausreichend fuer
typische persoenliche Use-Cases. Bei FMP-Fehler (Rate-Limit, Ticker
nicht gefunden, Network) faellt die Kette transparent auf YFinance,
StockData.org und schliesslich AlphaVantage zurueck.

NFR-Data-3 wird mit diesem Slice umgesetzt und auf APPROVED gesetzt.

## Scope (IN)

- `src/quant_trader/data/financial_modelling_prep.py` (neu):
  - `FinancialModellingPrepProvider` Klasse mit:
    - `name = "fmp"`
    - Konstruktor: `api_key: str | None = None` (Fallback auf
      `os.environ.get("FINANCIAL_MODELLING_PREP_KEY", "")`,
      `session: requests.Session | None = None`)
    - `fetch(ticker, start, end, granularity) -> list[Bar]`
    - Endpoint-Logik:
      - Daily: `GET https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}?from=YYYY-MM-DD&to=YYYY-MM-DD&apikey=XXX`
      - 60m: `GET .../historical-chart/1hour/{ticker}?from=...&to=...&apikey=XXX`
      - 15m: `GET .../historical-chart/15min/{ticker}?from=...&to=...&apikey=XXX`
    - Response-Parsing:
      - JSON `{"symbol": "SPY", "historical": [...]}` extrahieren
      - camelCase `adjClose` -> `adjusted_close` mappen
      - Daily `date` (YYYY-MM-DD) und Intraday `date` (YYYY-MM-DD HH:MM:SS) zu `datetime` parsen
      - Sortieren nach `timestamp` asc
      - Filter auf `start <= date <= end`
    - Error-Handling:
      - HTTP 200 mit `{"Error Message": "Invalid API KEY."}` -> `ProviderError(self.name, "invalid api key")`
      - HTTP 200 mit `{"Error Message": "Limit Reach ..."}` -> `RateLimitedError(self.name, ...)`
      - HTTP 401/403 -> `ProviderError(self.name, "auth failed")`
      - HTTP 429 -> `RateLimitedError(self.name, "HTTP 429")`
      - Network-Fehler (requests.RequestException) -> `ProviderError(self.name, f"network: {exc}")`
      - Leere `historical`-Liste -> `TickerNotFoundError(ticker)`
- `src/quant_trader/core/config.py`:
  - Neues Setting: `fmp_api_key: str = ""` (Default leer)
- `src/quant_trader/data/factory.py`:
  - Update: `primary = FinancialModellingPrepProvider(api_key=settings.fmp_api_key)`
  - Fallbacks: `YFinanceProvider, StockDataProvider, AlphaVantageProvider` (in dieser Reihenfolge)
  - Wenn `fmp_api_key` leer: Provider wird trotzdem erzeugt, wirft
    dann aber `ProviderError("API key not set")` beim ersten Fetch, was
    den Fallback triggert. (Akzeptabel fuer jetzt; keine Conditional
    Factory noetig.)
- `src/quant_trader/data/__init__.py`: exportiert `FinancialModellingPrepProvider`
- `tests/data/test_financial_modelling_prep.py` (neu, mind. 10 Tests):
  - Happy Path Daily: HTTP 200 + gueltige Response -> `list[Bar]`, sortiert
  - Happy Path 60m: HTTP 200 + gueltige Intraday-Response -> `list[Bar]`
  - Happy Path 15m: aehnlich
  - Empty Historical: `TickerNotFoundError`
  - `Error Message: "Invalid API KEY."` -> `ProviderError`
  - `Error Message: "Limit Reach ..."` -> `RateLimitedError`
  - HTTP 401 -> `ProviderError`
  - HTTP 429 -> `RateLimitedError`
  - Network Error (RequestException) -> `ProviderError`
  - Date-Filter: Bars ausserhalb [start, end] werden weggelassen
  - camelCase `adjClose` wird korrekt zu `adjusted_close` gemappt
  - Tests nutzen `responses` oder `requests-mock` (bevorzugt: `responses`,
    siehe `pyproject.toml`) oder `unittest.mock` mit `requests.Session`
- `tests/data/test_factory.py` (NEU, vorher gab es keinen direkten Test):
  - `build_chain(settings)` mit vollstaendigen Keys: Kette enthaelt FMP
    als Primary, dann YFinance, StockData, AlphaVantage
  - `build_chain(settings)` mit leerem fmp_key: Provider wird trotzdem
    erzeugt (kein Conditional-Skip)
- `docs/requirements/nfrs.md`: NFR-Data-3 von DRAFT auf APPROVED setzen
- `docs/STATE.md`: Slice 1.5 auf DONE markieren, Tag `p1-data/1.5`
- `docs/adr/0001-provider-chain-order.md`: Status auf "superseded by
  ADR-0009" setzen
- `docs/adr/0009-fmp-as-primary-provider.md`: Status von "proposed"
  auf "accepted" setzen

## Out of Scope (verbindlich)

- Auto-Refresh bei Rate-Limit (z.B. Retry nach 1h) - Free-Tier hat
  kein Auto-Retry-Slot
- Live-Streaming (FMP WebSocket) - Free-Tier nicht verfuegbar
- Andere Granularitaeten (1min, 5min, 30min, 4hour) - nur die 3
  bisher unterstuetzten (daily, 60m, 15m) werden gemappt
- Konfigurierbare Provider-Chain via Settings (YAGNI)
- Entfernung von AlphaVantageProvider (bleibt als letzter Fallback)
- Aenderung an ParquetCache oder DataService
- CLI-Aenderung (User fuegt FMP_KEY selbst in `.env` ein)

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies (requests ist bereits in `pyproject.toml`).
- Kein `print`, kein globaler State.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, Logs englisch.
- Tests deterministisch (gemockte HTTP, keine echte API).
- API-Key via `.env` (`FINANCIAL_MODELLING_PREP_KEY`), niemals im
  Repo committen (NFR-Sec-1).
- Free-Tier Rate-Limit 250 calls/Tag beachten (Logging warnt bei
  `RateLimitedError`, kein hard fail).

## Mapped NFRs

- NFR-Data-3 (FMP als Primary, DRAFT -> APPROVED mit diesem Slice)
- NFR-Sec-1 (API-Key via `.env`)
- NFR-Rel-1 (idempotenter Fetch, ueber bestehende DataService-Cache-
  Logik erfuellt)
- NFR-Perf-2 (5 Jahre < 60s, ueber FMP Endpoint-Response < 5s typisch)

## UML-Referenz

Visualisiert in: `docs/uml/p1-data/fmp-provider.md` (Status: wird auf
APPROVED gesetzt mit diesem Slice).

## Done when

- [ ] `src/quant_trader/data/financial_modelling_prep.py` mit
      `FinancialModellingPrepProvider` gemaess Scope.
- [ ] `src/quant_trader/core/config.py` hat `fmp_api_key: str = ""`.
- [ ] `src/quant_trader/data/factory.py` nutzt FMP als Primary, Kette
      in Reihenfolge: FMP -> YFinance -> StockData -> AlphaVantage.
- [ ] `tests/data/test_financial_modelling_prep.py` mit mind. 10
      Tests (alle HTTP-Fehlerfaelle + Happy Paths fuer daily/60m/15m).
- [ ] `tests/data/test_factory.py` neu mit Kette-Verifikation.
- [ ] `make test` gruen (alle 340 alten + neuen Tests).
- [ ] `make lint` gruen.
- [ ] `uv run mypy` gruen (ohne pre-existing logging.py).
- [ ] NFR-Data-3 auf APPROVED.
- [ ] ADR-0009 auf "accepted", ADR-0001 auf "superseded".
- [ ] Conventional Commit `feat(p1-data): slice 1.5 fmp provider primary`.
- [ ] `docs/STATE.md` aktualisiert: Slice 1.5 auf DONE, Tag
      `p1-data/1.5`.

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/adr/0009-fmp-as-primary-provider.md
cat docs/uml/p1-data/fmp-provider.md
cat docs/prd/p1-data/fmp-provider.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. Andere Provider NICHT
  aendern.
- Wenn etwas Off-Scope auftaucht: STOP, dokumentiere, frage Nutzer.

Nach dem Coden:
- Conventional Commit mit `feat(p1-data): slice 1.5 fmp provider primary`.
- Commit-Body: warum FMP (Free-Tier reicht), was verworfen wurde
  (z.B. konfigurierbare Chain via Settings).
