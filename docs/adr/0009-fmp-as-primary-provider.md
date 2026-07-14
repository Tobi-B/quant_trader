# ADR 0009: Financial Modelling Prep (FMP) als Primary Provider

Status:     accepted
Datum:      2026-07-14
Phase:      P1 Datenlayer
Supersedes: ADR-0001
Superseded by: -
Supersedes-Status: ADR-0001 (Provider-Chain-Reihenfolge) ist mit diesem Slice superseded.

## Context

Der bestehende Provider-Stack (ADR-0001) nutzt AlphaVantage als Primary,
weil dort ein Premium-Key hinterlegt ist. Der Trader moechte jetzt auf
Financial Modelling Prep (FMP) als **Haupt-API** umstellen, weil:

- FMP hat eine grosszuegige Free-Tier (250 calls/Tag), die fuer den
  persoenlichen Use-Case ausreicht
- FMP liefert konsistente Adjusted-Close-Daten ohne separate
  Corporate-Action-Tabellen
- FMP bietet sowohl daily als auch intraday (1min, 5min, 15min, 30min,
  1h, 4h) ueber dieselbe API

Die bestehenden Provider (YFinance, StockData.org, AlphaVantage) sollen
als Fallback erhalten bleiben, damit es keinen Single-Point-of-Failure
gibt.

## Decision

1. **Neuer Provider**: `FinancialModellingPrepProvider` in
   `src/quant_trader/data/financial_modelling_prep.py`, implementiert
   das `DataProvider`-Protocol.
2. **API-Key**: `fmp_api_key` wird zu `Settings` hinzugefuegt
   (`FINANCIAL_MODELLING_PREP_KEY` env-var), analog zu
   `alphavantage_key`.
3. **Provider-Chain** (in `src/quant_trader/data/factory.py`):

   ```
   Primary:    FinancialModellingPrepProvider(api_key=settings.fmp_api_key)
   Fallback 1: YFinanceProvider()
   Fallback 2: StockDataProvider(api_token=settings.stockdata_api_token)
   Fallback 3: AlphaVantageProvider(api_key=settings.alphavantage_key)
   ```

4. **Granularitaet**:
   - Daily: FMP `/historical-price-full/{ticker}` (Free-Tier ok)
   - Intraday 60m: FMP `/historical-chart/1hour/{ticker}` (Free-Tier ok)
   - Intraday 15m: FMP `/historical-chart/15min/{ticker}` (Free-Tier ok)
   - Bei FMP-Fehler (rate limit, ticker unknown, network): Fallback auf
     naechsten Provider in der Kette.

5. **Rate-Limit-Handling** (Free-Tier 250 calls/Tag):
   - FMP liefert `{"Error Message": "Limit Reach ..."}` (HTTP 200)
   - Provider wirft in diesem Fall `RateLimitedError` (kein silent
     retry), FallbackProvider schaltet weiter.
   - Logging: `provider.fallback` mit `provider=fmp`, `reason=...`
     (siehe ADR-0002).

6. **Response-Format**:
   - Daily: `{"symbol": "SPY", "historical": [{"date": "2024-01-02",
     "open": 100, "high": 101, "low": 99, "close": 100.5, "adjClose":
     100.5, "volume": 1000000}]}`
   - Intraday: `{"symbol": "SPY", "historical": [{"date":
     "2024-01-02 16:00:00", ...}]}`
   - Felder: camelCase (`adjClose`), wird zu snake_case (`adjusted_close`)
     gemappt.

## Consequences

**Positiv**
- 250 calls/Tag Free-Tier reicht fuer typische Backtests (1-5 Tickers
  x 1-3 Granularitaeten = 3-15 calls/Backtest, ~16 Backtests/Tag)
- Konsistente API fuer daily + intraday (kein Wechsel zu YFinance fuer
  Intraday noetig)
- Adjusted-Close direkt im Response (kein Nachberechnen)
- Fallback-Kette bleibt intakt, kein Single-Point-of-Failure

**Negativ**
- Free-Tier-Limit muss ueberwacht werden (kein Auto-Warn)
- 250 calls/Tag ist hart; bei > 16 Backtests/Tag schlagen FMP-Calls
  fehl (Fallback greift)
- FMP-Response-Format weicht von AlphaVantage ab (camelCase vs
  numerische Keys); zwei Parsing-Pfade noetig

**Neutral**
- ADR-0001 wird obsolet; wird im naechsten Cleanup geloescht oder mit
  Verweis auf ADR-0009 stehen gelassen
- Tests muessen das neue Response-Format mocken (Fixture-Files oder
  `unittest.mock`)

## Alternatives Considered

- **FMP-only ohne Fallback**: Single-Point-of-Failure, abgelehnt
- **FMP statt AlphaVantage ersetzen, andere Provider raus**: Breaking-
  Change, kein Mehrwert gegenueber Fallback-Erhalt, abgelehnt
- **FMP nur fuer daily, Intraday weiter YFinance**: Inkonsistent fuer
  den Trader; Free-Tier unterstuetzt 1h+15min ausreichend, abgelehnt
- **Provider-Chain via Settings konfigurierbar** (YAGNI): spaeterer
  Refactor billig, abgelehnt fuer jetzt

## References

- `src/quant_trader/data/financial_modelling_prep.py` (neu)
- `src/quant_trader/data/factory.py` (update)
- `src/quant_trader/core/config.py` (neues Setting `fmp_api_key`)
- `docs/prd/p1-data/fmp-provider.md` (Slice-PRD)
- `docs/uml/p1-data/fmp-provider.md` (Mermaid Structure/Flow/Sequence)
- FMP API Docs: https://financialmodelingprep.com/developer/docs/
- NFR-Data-3 (APPROVED)
- ADR-0001 (superseded)
- ADR-0002 (Fallback-Decorator-Pattern, bleibt aktiv)
