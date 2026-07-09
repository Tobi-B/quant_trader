# ADR 0002: Fallback-Pattern als Decorator-Klasse

Status:     accepted
Datum:      2026-07-10
Phase:      P1 (rueckwirkend dokumentiert)

## Context

Die Provider-Kette hat zwei unterscheidbare Fehlerfaelle:

1. **Ticker existiert nicht**: `TickerNotFoundError` — soll sofort propagieren, kein Fallback-Sinn (existiert auf keinem Provider).
2. **Provider technisch fehlgeschlagen**: `ProviderError` (z.B. HTTP 500, Rate-Limit, Scraping kaputt) — soll naechsten Provider versuchen.

Der Decorator-Ansatz muss:
- exakt wie ein Provider agieren (gleiche `fetch(ticker, start, end, granularity) -> list[Bar]`-Signatur)
- zur Laufzeit konfigurierbar sein (Reihenfolge, Anzahl Fallbacks)
- ohne Protocol-Anpassung am Caller auskommen

## Decision

`FallbackProvider` ist eine konkrete Klasse mit `__init__(primary, fallbacks: list)`, die intern `[primary, *fallbacks]` als Chain fuehrt. `fetch()` durchlaeuft die Chain, faengt `TickerNotFoundError` (re-raise) und `ProviderError` (log + continue), und liefert am Ende `DataUnavailableError(ticker, reasons)` wenn alle scheitern.

```python
class FallbackProvider:
    def __init__(self, primary, fallbacks: list) -> None: ...
    @property
    def name(self) -> str: return "fallback"
    def fetch(self, ticker, start, end, granularity) -> list[Bar]: ...
```

`name = "fallback"` ermoeglicht Logging-Identifikation, ohne dass Caller den Decorator kennen.

## Consequences

**Positiv**
- Duck-Typing: `FallbackProvider` ist strukturell kompatibel mit `DataProvider` Protocol
- Reihenfolge zur Laufzeit aenderbar (Constructor-Args)
- Klare Trennung: `TickerNotFoundError` fail-fast, `ProviderError` weiter
- Logging an der richtigen Stelle: jeder Fallback-Versuch wird geloggt mit Provider-Name und Grund

**Negativ**
- Keine Parallelisierung der Fallbacks (koennte bei Latenz helfen, aber Sequenz ist bei kleinem N ok)
- Eine zusaetzliche Indirektion (Class-Wrapper statt direktem Try/Except im Caller)

**Neutral**
- Erweiterbar um Timeout-Handling ohne API-Bruch

## Alternatives Considered

- **Chain-of-Responsibility mit `next`-Pointer**: jeder Provider haelt eine Referenz auf den naechsten — verworfen, weil mehr State und Boilerplate fuer 1 Use-Case
- **Strategy-Pattern mit Switch-Statement im Caller**: explizite Verzweigung — verworfen, weil Caller den Fallback-Mechanismus kennen wuerde
- **Funktionale Composition (`functools.reduce`)**: technisch elegant, aber fuer 3-4 Provider overkill

## References

- `src/quant_trader/data/fallback.py`
- `src/quant_trader/core/errors.py` (Error-Hierarchie)
- ADR 0001 (Provider-Chain-Reihenfolge)
