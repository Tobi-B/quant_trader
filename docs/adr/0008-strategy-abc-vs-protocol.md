# ADR 0008: StrategyBase als ABC statt Protocol

Status:     accepted
Datum:      2026-07-10
Phase:      P2 (Slice 2.1, rueckwirkend dokumentiert)

## Context

Im Data-Layer wird `DataProvider` als `Protocol` definiert (strukturelles Typing, keine Vererbung erforderlich). Bei Strategien stellt sich die Frage: gleicher Ansatz (Protocol) oder ABC mit Vererbung?

Strategien haben zusaetzlichen Bedarf, den Data-Provider nicht haben:
- **Default-Parameter**: jede Strategie hat sinnvolle Defaults (`fast=20, slow=50` fuer SMA-Cross), die in der Klasse selbst deklariert sind
- **Param-Merge**: User-YAML-Params sollen mit Defaults gemerged werden (User-Werte gewinnen)
- **Konsistenz**: alle Strategien sollen garantiert `name`, `warmup_bars()`, `on_bar()` haben — nicht "hoffentlich" via Duck-Typing

## Decision

`StrategyBase` und `MultiTickerStrategyBase` sind beide `ABC`s mit:
- ClassVar `name: str` (Registry-Key)
- ClassVar `version: str` (default `"1.0.0"`)
- ClassVar `default_params: dict[str, Any]` (default `{}`)
- `__init__(self, params: dict[str, Any] | None = None)`: merged `default_params` mit `params`
- `@abstractmethod warmup_bars() -> int`
- `@abstractmethod on_bar(bar, portfolio) -> list[Signal]` (bzw. `on_universe_bars` fuer MultiTicker)

Kein paralleles `Strategy`-Protocol — die ABCs sind die Schnittstelle.

```python
class StrategyBase(ABC):
    name: ClassVar[str] = ""
    version: ClassVar[str] = "1.0.0"
    default_params: ClassVar[dict[str, Any]] = {}

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = {**self.default_params, **(params or {})}

    @abstractmethod
    def warmup_bars(self) -> int: ...

    @abstractmethod
    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]: ...
```

## Consequences

**Positiv**
- Shared init/state: `default_params`-Merge ist zentral, nicht in jeder Strategie wiederholt
- Klare Subclass-Pflicht: `@abstractmethod` erzwingt `on_bar` und `warmup_bars`
- `isinstance(strategy, StrategyBase)` funktioniert fuer Type-Guards
- `super().__init__()` Pattern moeglich, falls zukuenftige Strategien weitere Init-Logik brauchen

**Negativ**
- Kein Duck-Typing ohne Vererbung: Klassen ohne expliziten `StrategyBase`-Subclass werden nicht akzeptiert
- ABC kann nicht mit `@runtime_checkable` wie Protocol verwendet werden (aber nicht noetig)
- Indirektion: 1-2 Klassen zwischen Caller und konkreter Strategie

**Neutral**
- `MultiTickerStrategyBase` ist separate ABC (kein gemeinsamer `Strategy`-Parent), weil die Signatur (`on_bar` vs. `on_universe_bars`) nicht vereinheitlicht werden kann

## Alternatives Considered

- **Protocol statt ABC**: verworfen — kein `default_params`-Merge ohne Boilerplate in jeder Strategie; `__init__` koennte in Protocol nicht erzwungen werden
- **Mixin-Pattern** (`ParamsMixin`, `NameMixin`): verworfen — komplexer, schwerer zu lesen
- **Dataclass mit `__post_init__`**: technisch elegant, aber `frozen=True` macht Param-Merge umstaendlich; `@abstractmethod` nicht direkt unterstuetzt
- **Single `Strategy` ABC mit `on_bar` als Default-Implementierung, die `NotImplementedError` wirft**: verworfen, weil MultiTicker-Strategien (Momentum, ETF-Rotation) `on_bar` gar nicht sinnvoll implementieren koennen

## References

- `src/quant_trader/strategies/base.py` (geplant, Slice 2.1)
- `src/quant_trader/data/provider.py` (im Gegensatz: Protocol)
- `docs/prd/p2-strategies/framework.md` (Slice-PRD, APPROVED)
- `docs/uml/p2-strategies/framework.md` (APPROVED, StrategyBase + MultiTickerStrategyBase)
