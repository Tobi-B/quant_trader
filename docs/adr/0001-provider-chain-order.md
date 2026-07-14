# ADR 0001: Provider-Chain-Reihenfolge AlphaVantage → YFinance → StockData

Status:     superseded by ADR-0009
Datum:      2026-07-10
Phase:      P1 (rueckwirkend dokumentiert)
Supersedes: -
Superseded by: 0009-fmp-as-primary-provider.md

## Context

Drei Daten-Provider sind verfuegbar, alle mit unterschiedlichen Eigenschaften:

- **AlphaVantage**: Premium-Account mit Key in `.env` (AlphaVantage Premium Endpoint aktiv). Datenqualitaet sehr gut, aber Quota pro Tag/Monat begrenzt; jeder Request verbraucht Credits.
- **YFinance**: Kostenlos, kein Key, breite Coverage (US + DE via `.DE`-Suffix), aber Scraping-basiert; Rate-Limits und Schema-Aenderungen sind moeglich.
- **StockData.org**: Free-Tier mit API-Token, als Fallback gedacht; nicht so zuverlaessig wie AV, aber breiter als YF bei exotischen Tickers.

Ziel: ein Ticker soll moeglichst zuverlaessig geladen werden, ohne die AV-Quota zu verbrennen, und die Kette soll transparent fuer den Code bleiben.

## Decision

Die Provider-Chain ist festgelegt in `src/quant_trader/data/factory.py`:

```
Primary:    AlphaVantageProvider(api_key=settings.alphavantage_key)
Fallback 1: YFinanceProvider()
Fallback 2: StockDataProvider(api_token=settings.stockdata_api_token)
```

`FallbackProvider` (Decorator) ruft die Chain in dieser Reihenfolge ab. `TickerNotFoundError` schlaegt sofort durch (fail-fast); `ProviderError` laesst den naechsten Provider versuchen. Wenn alle scheitern: `DataUnavailableError`.

## Consequences

**Positiv**
- AV-Quota wird nur angezapft, wenn kein billigerer Provider den Ticker liefern kann
- Bei Premium-Key-Besitz primaere Nutzung der hochwertigsten Quelle
- StockData als Reserve, falls YF-Rate-Limit oder Scraping-Problem

**Negativ**
- Reihenfolge ist im Code hartcodiert; zur Laufzeit nicht konfigurierbar ohne Code-Aenderung
- `TickerNotFoundError` von AV blockt den Fallback (korrekt, aber ueberraschend falls AV stale Daten liefert)

**Neutral**
- Factory ist klein, einfach zu testen; keine globale State

## Alternatives Considered

- **Round-Robin**: Provider nach Verfuegbarkeit rotieren — verworfen, weil keine Kostenueberwachung moeglich
- **AV-only**: Single-Provider ohne Fallback — verworfen, weil Single-Point-of-Failure und Quota-Risiko
- **Konfigurierbare Reihenfolge via Settings**: technisch moeglich, aber YAGNI fuer P1; spaeterer Refactor billig

## References

- `src/quant_trader/data/factory.py`
- `src/quant_trader/data/fallback.py`
- NFR-Perf-2 (5 Jahre < 60s, APPROVED)
- NFR-Rel-1 (Daten-Fetch idempotent, APPROVED)
