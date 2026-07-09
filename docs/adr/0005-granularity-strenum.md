# ADR 0005: Granularity als `StrEnum` mit `path_segment` Property

Status:     accepted
Datum:      2026-07-10
Phase:      P1 (rueckwirkend dokumentiert)

## Context

Granularity (daily, 60m, 15m) wird an 3+ Stellen verwendet:
1. CLI-Argument (String-Vergleich in argparse)
2. Cache-Pfad-Komponente (`data/raw/daily/`, `data/raw/60m/`, `data/raw/15m/`)
3. Provider-API-Parameter (z.B. `interval=60min` bei AV)

Die Werte sind endlich, stabil, und duerfen weder Tippfehler noch Erweiterungen ohne Code-Aenderung zulassen. Type-Safety ist erwuenscht, aber String-Kompatibilitaet (CLI, YAML, Env-Vars) auch.

## Decision

`Granularity` ist ein `enum.StrEnum` mit Property `path_segment`:

```python
class Granularity(StrEnum):
    DAILY = "daily"
    INTRADAY_60M = "60m"
    INTRADAY_15M = "15m"

    @property
    def path_segment(self) -> str:
        return str(self.value)
```

Damit gilt:
- `Granularity.DAILY == "daily"` → `True` (StrEnum-Magie)
- `str(Granularity.INTRADAY_60M) == "60m"` (fuer CLI-Output)
- `Granularity("60m")` Konstruktion aus String (CLI-Parsing)
- `granularity.path_segment` → `"60m"` (Cache-Pfad)
- mypy kennt `Granularity.DAILY` als `Literal["daily"]`

## Consequences

**Positiv**
- Type-Safe wo noetig (Function-Signaturen, mypy)
- String-kompatibel wo noetig (CLI, Logging, Cache-Pfade)
- `path_segment`-Property entkoppelt Enum-Name von Pfad-Darstellung (z.B. koennte `INTRADAY_60M.path_segment = "intraday_60m"` werden, ohne dass Aufrufer sich aendern)
- `StrEnum` ist Python 3.11+ Built-in, keine externe Dep

**Negativ**
- `StrEnum` ist 3.11+ — Python 3.10 nicht unterstuetzt (aber `pyproject.toml` pinned 3.11+)
- Property macht den Wert nicht direkt enumerable (aber das ist nicht noetig)

**Neutral**
- Neue Granularity hinzufuegen = Code-Aenderung + Cache-Pfad-Aenderung (akzeptabel)

## Alternatives Considered

- **`enum.Enum` ohne Str-Mixin**: verworfen — keine native YAML/CLI/Logging-Lesbarkeit (`Granularity.DAILY.value == "daily"` aber nicht `== "daily"`)
- **Literal-Types**: `granularity: Literal["daily", "60m", "15m"]` — verworfen, weil keine Path-Property moeglich und keine zentrale Stelle fuer Liste
- **Pydantic-Enum**: verworfen, weil Overhead und Doppelpflege
- **Konstante Strings**: verworfen, weil keine Type-Safety und keine zentrale Liste

## References

- `src/quant_trader/core/types.py` (Granularity-Definition)
- `src/quant_trader/data/cache.py` (path_segment fuer Pfad)
- `src/quant_trader/data/cli.py` (argparse `choices=[g.value for g in Granularity]`)
- `src/quant_trader/data/factory.py` (an Provider durchgereicht)
