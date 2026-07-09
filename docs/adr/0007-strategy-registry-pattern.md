# ADR 0007: Strategy-Registry-Pattern

Status:     accepted
Datum:      2026-07-10
Phase:      P2 (rueckwirkend dokumentiert fuer Slice 2.1; weitere Strategien in 2.2-2.4)

## Context

Strategien sollen:
- zur Laufzeit aus YAML instanziiert werden koennen, ohne dass der Backtest/Runner die konkreten Klassen kennt
- in unabhaengigen Modulen/Slices implementiert werden (SMA-Cross in 2.2, RSI in 2.3, ETF-Rotation in 2.4)
- ueber einen Namen in `config/strategies.yaml` referenzierbar sein
- typensicher sein (mypy kennt den Rueckgabetyp)

Der Backtest-/Runner-Code soll nur mit dem Strategy-Interface sprechen, nicht mit konkreten Klassen. Neue Strategien sollen ohne Aenderung des Backtest/Runner-Codes einbindbar sein.

## Decision

`StrategyLoader` ist ein zentrales Registry-Pattern:

```python
class StrategyLoader:
    def __init__(self, config_path: Path) -> None:
        self._registry: dict[str, type[StrategyBase]] = {}
        self._config: dict[str, dict[str, Any]] = {}

    def register(self, cls: type[StrategyBase]) -> None:
        # Name kommt aus cls.name (ClassVar)
        # Konflikt (zwei Klassen mit gleichem Namen) wirft StrategyError
        ...
        self._registry[cls.name] = cls

    def registered_names(self) -> list[str]: ...

    def load(self, name: str) -> StrategyBase:
        # liest YAML, merged params mit default_params, instanziiert
        ...
```

`register(cls)` nimmt **keinen** expliziten Namen; der Registry-Key ist `cls.name` (ClassVar auf `StrategyBase`). Konflikt-Detection: zwei Klassen mit gleichem `name` → `StrategyError` beim Register.

YAML-Format:
```yaml
sma_cross:
  params:
    fast: 20
    slow: 50
rsi_mean_reversion:
  params:
    period: 14
    oversold: 30
    overbought: 70
```

## Consequences

**Positiv**
- Backtest kennt nur `StrategyBase` Protocol/ABC; neue Strategien ohne Code-Aenderung am Caller einbindbar
- Strategien koennen in eigenen Modulen implementiert sein (`strategies/sma_cross.py`, `strategies/rsi.py`, ...)
- `register(cls)` ist explizit (kein Magic via Decorators oder `__init_subclass__`)
- `registered_names()` liefert sortierte Liste fuer Fehlermeldungen

**Negativ**
- Kein Hot-Reload (YAML-Aenderung erfordert Neustart)
- Kein Plugin-System via `importlib` (Strategien muessen explizit registriert werden, typischerweise im `__init__.py` des jeweiligen Moduls)
- Reihenfolge der Registrierung ist nicht garantiert deterministisch (aber `sorted()` macht es stabil)

**Neutral**
- Konfigurations-Validierung ist konservativ (fehlende Section → Fehler), keine Schema-Validierung per Pydantic

## Alternatives Considered

- **Pydantic-Discriminator-Tagged-Unions**: `Annotated[Union[SmaCrossParams, RsiParams], Field(discriminator="type")]` — verworfen, weil zu starr fuer dynamische YAML
- **Plugin-System via `importlib`**: Strategien aus separaten Packages automatisch laden — verworfen als YAGNI fuer Phase 2; Out of Scope im PRD
- **Decorator-Pattern auf Strategy-Klasse** (`@register_strategy`): eleganter, aber implizit — verworfen zugunsten expliziter `register(cls)`-Aufrufe im `__init__.py`
- **Entry-Points (setuptools)**: professionell, aber Overhead fuer ein einzelnes Package

## References

- `src/quant_trader/strategies/loader.py` (geplant, Slice 2.1)
- `src/quant_trader/strategies/base.py` (geplant, Slice 2.1)
- `config/strategies.yaml` (geplant, Slice 2.1)
- `docs/prd/p2-strategies/framework.md` (Slice-PRD, APPROVED)
- `docs/uml/p2-strategies/framework.md` (APPROVED)
