# PRD: Slice 2.1 - Strategy Framework

Phase:    P2 Strategien
Slice:    2.1 Strategy Framework
Status:   DRAFT  (wartet auf User-APPROVED)
Author:   opencode
Created:  2026-07-10
Updated:  2026-07-10

## Goal

Ein einheitliches Strategy-Framework bereitstellen, das alle konkreten
Strategien (SMA-Cross, Momentum, RSI, ETF-Rotation) ueber die gleiche
Schnittstelle ansprechbar macht und Parameter zur Laufzeit aus einer
YAML-Datei ladt - ohne dass dafuer Python-Code angefasst werden muss.

## Scope (IN)

- `quant_trader.strategies.types`
  - `Action` (StrEnum: BUY, SELL, HOLD)
  - `Signal` (frozen dataclass: timestamp, ticker, action, reason)
  - `PortfolioState` (frozen dataclass: cash float, positions dict[str, int])
    - Stub fuer Phase 3; `positions` haelt Aktien-Anzahl pro Ticker
  - `StrategyConfig` (frozen dataclass: strategy_name, params)
- `quant_trader.strategies.errors`
  - `StrategyError` (Basis)
  - `StrategyConfigError` (Config-Datei fehlt/Section fehlt/falscher Typ)
  - `UnknownStrategyError` (Strategie nicht in Registry; traegt Liste der
    verfuegbaren Strategien)
- `quant_trader.strategies.base`
  - `StrategyBase` (ABC mit Default-Param-Merge, abstrakte Methoden
    `warmup_bars` und `on_bar`; ClassVar `name`, `version`, `default_params`)
  - `MultiTickerStrategyBase` (ABC mit `warmup_bars` und `on_universe_bars`
    fuer Universe-basierte Strategien wie Momentum und ETF-Rotation)
- `quant_trader.strategies.loader`
  - `StrategyLoader(config_path)` mit:
    - `register(cls)` (validiert Subclass-Beziehung zu `StrategyBase` oder
      `MultiTickerStrategyBase`; Name kommt aus `cls.name` ClassVar)
    - `registered_names() -> list[str]`
    - `load(name) -> StrategyBase` (liest YAML, merged params, instanziiert)
- `config/strategies.yaml` (Skeleton mit Beispiel-Section, auskommentiert)
- `core.config.Settings.strategies_config_path` (default
  `./config/strategies.yaml`)
- `quant_trader.strategies` Package-`__init__.py` mit Public-API
- Tests: types, base, loader (YAML laden, Registry-Mechanik, klare Fehler)

## Out of Scope (verbindlich)

- Konkrete Strategien (SMA-Cross, Momentum, RSI, ETF-Rotation) - Slices 2.2-2.4.
- Signal-Runner-CLI (`python -m quant_trader.strategies run`) - Slice 2.5.
- Backtest-Engine und P&L-Berechnung - Phase 3.
- Portfolio-Management (Cash, Equity, P&L) - Phase 3, hier nur Stub-Typ.
- Live-Reload der YAML waehren eines laufenden Backtests.
- Hot-Reload, File-Watcher, UI fuer Parameter.
- Persistenz von Strategie-Signalen (kommt mit Journal in Phase 5).

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies (`pyyaml` ist bereits in `pyproject.toml`).
- Kein `print`, kein globaler State, kein Wildcard-Import.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, CLI-Strings deutsch, Logs englisch.
- StrategyBase-Subklassen muessen `name` (str) und (optional) `version` (str)
  als ClassVar deklarieren; `default_params` (dict[str, Any]) als ClassVar.
- `register(cls)` nimmt **keinen** expliziten Namen; der Registry-Key ist
  `cls.name`. Konflikt (zwei Klassen mit gleichem Namen) wirft
  `StrategyError`.
- Registry-Pattern: `StrategyLoader` weiss nichts ueber konkrete Strategien;
  in 2.1 bleibt die Registry leer (konkrete Klassen kommen in 2.2-2.4).
- YAML-Laden ist `safe_load`; Pydantic-Settings-Config-Pfad analog zu
  `universe_presets_path`.

## Mapped NFRs

- NFR-Ux-1 (klare API, deutsche Fehlermeldungen): konsistente Schnittstelle
  ueber alle Strategien, `UnknownStrategyError.message` listet verfuegbare
  Namen auf.
- NFR-Sec-1 (keine Secrets in YAML): YAML-Loader akzeptiert nur `params`-
  Mapping; keine `key`/`token`/`secret`-Felder. (Validierung nicht
  erzwungen, aber Konvention dokumentiert; Phase 5 erweitert ggf.)
- NFR-Obs-1 (structlog): `StrategyLoader.load` loggt `strategy.loaded`
  mit Name und Param-Count.

## UML-Referenz

Visualisiert in: `docs/uml/p2-strategies/framework.md` (Status: APPROVED)

## Done when

- [ ] `src/quant_trader/strategies/` enthaelt `types.py`, `base.py`,
      `loader.py`, `errors.py`, `__init__.py` gemaess Scope.
- [ ] `config/strategies.yaml` existiert als kommentiertes Skeleton.
- [ ] `Settings.strategies_config_path` mit Default
      `./config/strategies.yaml`.
- [ ] Tests: `tests/strategies/test_types.py`, `test_base.py`,
      `test_loader.py` decken Scope ab.
- [ ] `make test` gruen (alle alten + neuen Tests).
- [ ] `make lint` gruen (ruff check + format --check).
- [ ] `uv run mypy` gruen (--strict).
- [ ] Conventional Commit `feat(p2-strategies): slice 2.1 strategy framework`.
- [ ] `docs/STATE.md` aktualisiert (Slice-Status: IN_PROGRESS -> DONE,
      Tag `p2-strategies` bleibt offen, bis alle Sub-Slices durch sind).

## Anti-Drift-Reminder

Vor dem Coden:

```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p2-strategies/strategies.md
cat docs/uml/p2-strategies/framework.md
cat docs/prd/p2-strategies/framework.md   # diese Datei
```

Waehrend des Codens:

- Tue **nur** das, was in `Scope (IN)` steht. Konkrete Strategien gehoeren
  in 2.2-2.4, der Runner gehoert in 2.5.
- Wenn etwas Off-Scope auftaucht: STOP, dokumentiere in Commit-Body oder
  STATE.md, frage Nutzer.
- Wenn Tests fehlschlagen: **erst** Tests verstehen, dann Code fixen.

Nach dem Coden:

- Conventional Commit mit `feat(p2-strategies): slice 2.1 strategy framework`.
- Commit-Body enthaelt: warum Protocol+ABC (Data-Layer-Konsistenz), was
  verworfen wurde (z.B. direkter Pydantic-Config-Loader zugunsten einfacher
  `dict`-Params).
