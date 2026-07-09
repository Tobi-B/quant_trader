# ADR 0006: `ib_insync` als IBKR-Broker-Adapter (Phase 5, geplant)

Status:     proposed
Datum:      2026-07-10
Phase:      P5 (geplant, noch nicht implementiert)

> **Hinweis**: Status `proposed`, weil Phase 5 noch nicht implementiert ist. Bei Implementierung
> wird der Status auf `accepted` geaendert (oder superseded, falls sich Anforderungen aendern).

## Context

Interactive Brokers (IBKR) ist der Ziel-Broker fuer Live-Trading. Die offizielle API ist `ibapi` (C++-Wrapper mit Python-Bindings), hat aber folgende Schmerzen:
- Asynchroner Event-Loop mit Callbacks, der schwer zu testen ist
- C++-DLL muss auf Zielplattform vorhanden sein
- Doku duenn, Fehlermeldungen kryptisch
- Community klein im Vergleich zu `ib_insync`

Alternativen:
- `ib_insync`: Python-async-Wrapper, der auf `ibapi` aufsetzt, aber eine saubere Coroutine-API bietet
- `traderpy`: aelterer Wrapper, kaum Maintainer
- Native `ibapi`: wie oben

## Decision

`ib_insync` wird als Broker-Adapter gewaehlt. Paper-Trading zuerst (TWS Paper-Account), dann Live (TWS Live-Account). Anbindung ueber `127.0.0.1:7497` (Paper) bzw. `7496` (Live) im `.env`.

```python
# geplant
from ib_insync import IB, Stock, MarketOrder, LimitOrder
from quant_trader.live.adapter import BrokerAdapter  # Protocol

class IbInsyncAdapter:
    def __init__(self, host: str, port: int, client_id: int) -> None: ...
    def connect(self) -> None: ...
    def submit_order(self, order: Order) -> str: ...  # returns client_order_id
    def positions(self) -> list[Position]: ...
    def disconnect(self) -> None: ...
```

Reconnect-Handling (NFR-Rel-2) ueber `ib_insync`-eigenes `Connection`-Event.

## Consequences

**Positiv**
- async/await-Pattern passt zu zukuenftiger Streamlit-UI und Live-Loop
- Aktive Community, gute Doku
- Eingebautes Reconnect-Handling fuer TWS-Disconnects
- Type-Hints im Source (modernes Python)

**Negativ**
- Externe Abhaengigkeit mit eigener Versionspolitik (Major-Breaks moeglich)
- Indirekte Abhaengigkeit zu `ibapi` (C++-DLL)
- Lizenz: LGPL (kompatibel mit proprietärem Use-Case, aber pruefen)

**Neutral**
- `ib_insync` ist single-threaded async; multi-Account-Strategien brauchen mehrere `IB()`-Instanzen

## Alternatives Considered

- **Native `ibapi`**: verworfen — C-Bindings-Schmerz, schlechte Testbarkeit
- **`traderpy`**: verworfen — kaum Maintainer, eingeschlafene Community
- **Eigener Wrapper um `ibapi`**: verworfen — Re-implementierung von `ib_insync` ohne Mehrwert
- **Anderer Broker (Alpaca, Tradier)**: out of scope; IBKR ist Persona-Anforderung

## Implementation Plan (Phase 5)

1. `src/quant_trader/live/adapter.py` mit `BrokerAdapter` Protocol
2. `src/quant_trader/live/ib_insync_adapter.py` mit `IbInsyncAdapter`
3. `src/quant_trader/live/manager.py` mit Reconnect-Loop und Heartbeat
4. `src/quant_trader/storage/journal.py` fuer Trade-Journal in SQLite
5. Tests mit `pytest-mock` (keine echte TWS noetig fuer Unit-Tests; Integration-Tests als `live`-Marker)

## References

- `pyproject.toml` (`live = ["ib_insync>=0.9.86"]`)
- NFR-Sec-2 (Broker-Credentials via TWS, DRAFT)
- NFR-Rel-2 (TWS-Auto-Reconnect, DRAFT)
- NFR-Rel-3 (Order-Manager idempotent, DRAFT)
- NFR-Obs-2 (Tageszusammenfassung, DRAFT)
