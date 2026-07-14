# PRD: Slice 5.1 - Broker Interface + Mock + Order

Phase:    P5 Live-Trading (IBKR)
Slice:    5.1 Broker Interface + Mock + Order (Foundation)
Status:   DRAFT  (User "weiter mit naechstem slice" gilt als implizite Approval; UML auf APPROVED setzen)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Eine einheitliche `BrokerClient`-Abstraktion schaffen, ueber die
Strategien (Phase 2) Orders platzieren koennen - sowohl im Test
(`MockBroker`, deterministisch, ohne TWS) als auch im Live-Betrieb
(`IBKRBroker` via `ib_insync`). `Order`-Datentypen mit Status-State-
Machine sind die Sprache zwischen Strategie und Broker. ib_insync
bleibt ein optionales `live` extra, sodass CI ohne TWS lauffaehig ist.

Slice 5.2 (Live Loop), 5.3 (Auto-Reconnect), 5.4 (Tageszusammenfassung)
und 5.5 (CLI + Credentials) folgen auf 5.1.

## Scope (IN)

- `src/quant_trader/live/` Sub-Package (NEU):
  - `__init__.py` mit Public-API
  - `types.py`:
    - `OrderStatus` (StrEnum: PENDING, SUBMITTED, FILLED, CANCELLED, REJECTED)
    - `OrderType` (StrEnum: MARKET, LIMIT)
    - `Order` (frozen dataclass): id, client_order_id, ticker, action,
      qty, type, status, filled_qty, avg_fill_price, created_at,
      updated_at
    - `Position` (frozen dataclass): ticker, qty, avg_cost (initial 0.0,
      leer)
  - `protocol.py`:
    - `BrokerClient` Protocol mit Methoden:
      - `is_connected() -> bool`
      - `place_order(ticker, action, qty) -> Order`
      - `get_positions() -> dict[str, int]` (ticker -> qty)
      - `cancel_order(client_order_id) -> bool`
  - `mock.py`:
    - `MockBroker(fill_price: float = 100.0)` Klasse:
      - State: `_orders: dict[client_order_id, Order]`, `_positions:
        dict[ticker, int]`
      - `place_order`: erstellt Order mit `status=SUBMITTED`, dann
        sofort via internem `_execute(order)` -> `status=FILLED`,
        `filled_qty=qty`, `avg_fill_price=fill_price`, `updated_at`,
        Position-Update
      - Bei `qty <= 0`: Order mit `status=REJECTED`
      - `get_positions`: returnt `dict(self._positions)`
      - `cancel_order(client_order_id)`:
        - PENDING/SUBMITTED -> CANCELLED, return True
        - FILLED -> no-op, return False
        - Unknown -> return False
      - `is_connected()`: True
      - Tests OHNE Random, OHNE Time-Sleep, OHNE Network
  - `ibkr.py`:
    - `IBKRBroker(host, port, client_id)` Klasse:
      - `import ib_insync` am Modul-Anfang mit `try/except ImportError`
        -> `SystemExit` (deutsche Meldung "ib_insync nicht installiert.
        Bitte `uv sync --extra live`")
      - `place_order`: legt `MarketOrder` via `ib_insync` an, ID =
        `ib.orderId` (Stub in Slice 5.1: raise `NotImplementedError` mit
        Hinweis auf 5.2)
      - `is_connected()`, `get_positions()`, `cancel_order()`:
        Stub mit `NotImplementedError` und Slice-5.2-Hinweis
      - KEINE echte TWS-Connection in 5.1 (kommt in 5.2)
  - `factory.py`:
    - `build_broker(settings) -> BrokerClient`:
      - `if settings.live_enabled: return IBKRBroker(...)`
      - `else: return MockBroker(fill_price=settings.mock_fill_price)`
- `src/quant_trader/core/config.py` (aendern):
  - `Settings`-Erweiterung:
    - `live_enabled: bool = False`
    - `ibkr_host: str = "127.0.0.1"`
    - `ibkr_port: int = 7497` (Paper-Default)
    - `ibkr_client_id: int = 1`
    - `mock_fill_price: float = 100.0`
- `src/quant_trader/__init__.py`: nichts (live ist eigenstaendiges Modul)
- Tests: `tests/live/` (NEU):
  - `__init__.py`
  - `test_mock_broker.py` (mind. 10 Tests):
    - `test_place_order_returns_order_with_submitted_status`
    - `test_place_order_executes_synchronously_to_filled`
    - `test_place_order_updates_positions_on_fill`
    - `test_place_order_with_zero_qty_is_rejected`
    - `test_place_order_with_negative_qty_is_rejected`
    - `test_get_positions_returns_current_holdings`
    - `test_cancel_pending_order_succeeds`
    - `test_cancel_filled_order_fails`
    - `test_cancel_unknown_order_fails`
    - `test_is_connected_returns_true`
    - `test_client_order_id_is_unique_across_orders`
    - `test_multiple_orders_in_sequence_track_correctly`
  - `test_factory.py` (mind. 3 Tests):
    - `test_factory_returns_mock_by_default`
    - `test_factory_returns_mock_when_live_disabled`
    - `test_factory_uses_settings_for_mock_fill_price`

## Out of Scope (verbindlich)

- Echte IBKR-Connection (TWS-Port, Asyncio-Event-Loop) - Slice 5.2
- Limit-Orders / Stop-Orders / Trailing-Stops (nur MARKET in P5)
- Options / Futures (nur Stocks/ETFs)
- Short-Selling / Margin
- Auto-Reconnect bei TWS-Disconnect (Slice 5.3)
- Tageszusammenfassung (Slice 5.4)
- Credentials-Persistierung / TWS-Auth-Flow (Slice 5.5)
- BacktestEngine-Integration (BacktestEngine nutzt weiterhin `Fill`-Simulator)
- Strategie-Migration auf `BrokerClient` (Strategien nutzen weiterhin `Signal`; Bridge in 5.2)
- BacktestEngine -> BrokerClient-Adapter (Slice 5.2)
- Trade-Journal in SQLite (kommt mit Slice 5.2)
- Live-Loop (Connect, Subscribe, on_bar -> order) (Slice 5.2)
- ib_insync-Integration mit asyncio-Event-Loop (Slice 5.2)

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies (ib_insync ist bereits in `pyproject.toml` als `live` extra).
- Kein `print`, kein globaler State.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, CLI-Strings deutsch (bei User-facing Fehlermeldungen).
- ib_insync-Import NUR in `ibkr.py` (try/except), niemals in `mock.py`,
  `factory.py` oder Tests. So bleibt CI ohne `live` extra lauffaehig.
- `Order` ist frozen; Status-Updates erzeugen neue Instanzen
  (via `_with_status(order, **changes)` Helper in `MockBroker`).
- `MockBroker` ist deterministisch: `fill_price` aus Settings, kein
  Random, kein Time-Sleep, kein Network.
- Backward-Compat: bestehende 378 Tests unveraendert gruen.

## Mapped NFRs

- NFR-Rel-3 (Order-Manager idempotent: gleiche ClientOrderId nicht
  zweimal senden) - via UUID `client_order_id`; vollstaendige
  Idempotenz-Logik in 5.2
- NFR-Sec-2 (Credentials via TWS only) - relevant fuer 5.5;
  Slice 5.1 hat keine Credentials im Code (nur host/port/client_id)
- NFR-Obs-1 (structlog) - MockBroker loggt `broker.order_placed`,
  `broker.order_filled`, `broker.order_rejected` mit allen relevanten Feldern

## UML-Referenz

Visualisiert in: `docs/uml/p5-live/broker-interface.md` (Status: wird auf
APPROVED gesetzt mit diesem Slice).

## Done when

- [ ] `src/quant_trader/live/` mit allen Modulen gemaess Scope.
- [ ] `Settings` hat `live_enabled`, `ibkr_host`, `ibkr_port`,
      `ibkr_client_id`, `mock_fill_price` mit Defaults.
- [ ] Tests in `tests/live/` decken `MockBroker` + `BrokerFactory` ab.
- [ ] `make test` gruen (alle 378 alten + neuen Tests).
- [ ] `make lint` gruen.
- [ ] `mypy --strict` gruen (0 errors).
- [ ] ib_insync NICHT in `mock.py` / `factory.py` / Tests importiert.
- [ ] Conventional Commit `feat(p5-live): slice 5.1 broker interface`.
- [ ] `docs/STATE.md` aktualisiert: Slice 5.1 auf DONE, Tag `p5-live/5.1`.
- [ ] ADR-0011 auf "accepted".

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p5-live/live.md
cat docs/adr/0011-broker-interface-architecture.md
cat docs/uml/p5-live/broker-interface.md
cat docs/prd/p5-live/broker-interface.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. Echte IBKR-Connection
  in 5.2, Auto-Reconnect in 5.3, etc.
- **KRITISCH**: ib_insync nur in `ibkr.py`. Mock-Tests ohne live extra.
- Wenn etwas Off-Scope auftaucht: STOP, dokumentiere, frage Nutzer.

Nach dem Coden:
- Conventional Commit mit `feat(p5-live): slice 5.1 broker interface`.
- Commit-Body: warum Protocol statt ABC (Pattern ADR-0008), warum
  MockBroker deterministisch (CI ohne Random), warum `client_order_id`
  als UUID (Idempotenz NFR-Rel-3).
