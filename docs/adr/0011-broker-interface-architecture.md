# ADR 0011: Broker-Interface-Architektur (Protocol + Mock + IBKR)

Status:     proposed
Datum:      2026-07-14
Phase:      P5 Live-Trading
Supersedes: -
Superseded by: -

## Context

Phase 5 (Live-Trading) braucht eine einheitliche Broker-Schnittstelle,
die sowohl den realen IBKR (via `ib_insync`) als auch einen
deterministischen Mock fuer Tests anspricht. Die Strategien aus Phase
2 sollen ohne Aenderung sowohl in Backtests (Phase 3) als auch in
Live-Trading laufen koennen.

Im Repo existieren:
- `strategies/types.py` mit `Action` (StrEnum: BUY, SELL, HOLD) und
  `Signal` (frozen dataclass)
- `pyproject.toml` hat `live = ["ib_insync>=0.9.86"]` als optional
  extra; `ib_insync` ist NICHT im Default-Env installiert

## Decision

### 1. Module-Struktur

```
src/quant_trader/live/
  __init__.py
  types.py        # Order, OrderStatus, OrderType, Position
  protocol.py     # BrokerClient Protocol
  mock.py         # MockBroker
  ibkr.py         # IBKRBroker (try/except import ib_insync)
  factory.py      # BrokerFactory
```

### 2. `BrokerClient` Protocol

```python
class BrokerClient(Protocol):
    def is_connected(self) -> bool: ...
    def place_order(self, ticker: str, action: Action, qty: int) -> Order: ...
    def get_positions(self) -> dict[str, int]: ...   # ticker -> qty
    def cancel_order(self, client_order_id: str) -> bool: ...
```

### 3. `Order` Dataclass (frozen)

- `id: str` (Broker-interne ID; bei IBKR: orderId; bei Mock: UUID)
- `client_order_id: str` (vom Broker generiert, idempotent, NFR-Rel-3)
- `ticker: str`
- `action: Action`
- `qty: int`
- `type: OrderType` (MARKET in P5)
- `status: OrderStatus` (initial: SUBMITTED fuer Mock, PENDING fuer IBKR)
- `filled_qty: int` (initial 0)
- `avg_fill_price: float | None` (initial None)
- `created_at: datetime`
- `updated_at: datetime`

### 4. `OrderStatus` (StrEnum)

`PENDING`, `SUBMITTED`, `FILLED`, `CANCELLED`, `REJECTED`

### 5. `OrderType` (StrEnum)

`MARKET`, `LIMIT` (nur MARKET in P5, aber Enum ist zukunftssicher)

### 6. `MockBroker` (testbar, deterministisch)

- `place_order`: erstellt Order mit Status=SUBMITTED, dann sofort
  FILLED (synchron). Fill-Preis: konfigurierbar (Default: 100.0) fuer
  deterministische Tests. Qty-Mismatch: REJECTED.
- `get_positions`: returnt interne `dict[str, int]`
- `cancel_order`: PENDING/SUBMITTED -> CANCELLED, FILLED -> no-op (False)
- State: `dict[client_order_id, Order]`, `dict[ticker, qty]`
- Konstruktor: `MockBroker(fill_price: float = 100.0)`
- `is_connected()`: True (immer)
- KEIN Random, KEIN Time-Sleep, KEIN Network

### 7. `IBKRBroker` (Stub fuer Slice 5.1, vollstaendig in 5.2)

- `import ib_insync` mit try/except ImportError -> SystemExit
  (deutsche Meldung: "ib_insync nicht installiert. `uv sync --extra live`")
- `place_order`: legt `MarketOrder` an, ruft `ib.placeOrder()`, ID =
  `ib.orderId` (von ib_insync allokiert)
- `is_connected()`: True nach erfolgreichem `connect()`, sonst False
- `get_positions()`: liest `ib.positions()` und mappt zu dict
- Status-Polling: in Slice 5.2 implementiert (Trade-Callback)
- In Slice 5.1: Methoden koennen `NotImplementedError` werfen mit Hinweis
  "Vollstaendige IBKR-Integration in Slice 5.2"

### 8. `BrokerFactory`

```python
def build_broker(settings: Settings) -> BrokerClient:
    if settings.live_enabled:
        return IBKRBroker(host=settings.ibkr_host, port=settings.ibkr_port,
                          client_id=settings.ibkr_client_id)
    return MockBroker(fill_price=settings.mock_fill_price)
```

- `MockBroker` ist IMMER verfuegbar (kein ib_insync-Import noetig)
- `IBKRBroker` nur bei `live_enabled=True` (lazy import)
- Settings: `live_enabled: bool = False`, `ibkr_host: str = "127.0.0.1"`,
  `ibkr_port: int = 7497` (Paper), `ibkr_client_id: int = 1`,
  `mock_fill_price: float = 100.0`

### 9. ib_insync-Handling

- `IBKRBroker` (in `ibkr.py`) importiert `ib_insync` am Modul-Anfang
  mit try/except ImportError; bei fehlendem Modul `SystemExit` mit
  deutscher Installations-Anleitung
- `BrokerFactory.build_broker` mit `live_enabled=True` OHNE
  installiertes ib_insync -> `SystemExit` (sauberer Fehler)
- `MockBroker` hat KEINEN ib_insync-Import (Tests ohne live extra)

## Consequences

**Positiv**
- Strategien koennen ohne Aenderung in Tests (Mock) und Live (IBKR) laufen
- `MockBroker` ist deterministisch, schnelle Tests ohne TWS
- `BrokerClient` Protocol ermoeglicht Dependency Injection
- ib_insync-Import nur bei Bedarf (CI ohne live extra lauffaehig)
- `client_order_id` als UUID ist idempotent (NFR-Rel-3 erfuellt)

**Negativ**
- `IBKRBroker` ist in Slice 5.1 nur Stub (echte Logik in 5.2)
- Asynchrone IBKR-API (ib_insync nutzt event loop) braucht
  besondere Behandlung in 5.2
- MockBroker ist zu simpel (kein Partial-Fill, keine Latency)
  - Akzeptabel fuer Unit-Tests; Live-Tests brauchen IBKR-Paper

**Neutral**
- `Order` ist frozen, kann nicht mutiert werden; Status-Updates
  erzeugen neue Order-Instanzen (via `_with_status`-Helper in MockBroker)
- Kein neuer ADR-Status; Pattern folgt ADR-0007 (Strategy-Registry)

## Alternatives Considered

- **MockBroker als Protocol-Stub nur fuer Type-Hints**: abgelehnt,
  MockBroker muss echte Logik fuer Tests haben
- **Order als mutable dataclass**: abgelehnt, frozen ist
  konsistent mit `Signal`, `Trade`, `EquitySnapshot`
- **ib_insync als required dependency**: abgelehnt, CI soll ohne
  TWS laufen koennen
- **Order-ID als Auto-Increment**: abgelehnt, UUID ist robuster
  (kein Collisions-Risiko bei Reconnects)
- **MockBroker im tests/ Ordner**: abgelehnt, MockBroker ist
  produktiver Code (kann in Demo-Notebooks genutzt werden)

## References

- `src/quant_trader/live/` (neu, Slice 5.1)
- `src/quant_trader/strategies/types.py` (`Action` reused)
- `src/quant_trader/core/config.py` (`Settings` Erweiterung)
- `docs/userstories/p5-live/live.md` (US-P5.1)
- `docs/prd/p5-live/broker-interface.md` (Slice-PRD)
- `docs/uml/p5-live/broker-interface.md` (Mermaid Structure/Flow/Sequence)
- ADR-0007 (Strategy-Registry-Pattern, Pattern-Vorlage)
- ADR-0008 (Strategy-ABC-vs-Protocol, Protocol statt ABC)
- NFR-Rel-3 (Order-Manager idempotent)
- NFR-Sec-2 (Credentials via TWS only, Slice 5.5)
