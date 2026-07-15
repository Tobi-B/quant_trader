# ADR 0016: Strategy Documentation Viewer (README pro Strategie + Dashboard)

Status:     accepted
Datum:      2026-07-15
Phase:      P2 Strategien (Erweiterung)
Supersedes: -
Superseded by: -

## Context

Der Trader ist ein Anfaenger und moechte die registrierten Strategien
verstehen OHNE den Python-Code lesen zu muessen. Die Strategien
(SmaCross, Momentum, RSI-Mean-Reversion, ETF-Rotation) sind
funktional in Phase 2 implementiert, aber es gibt keine zentrale
Dokumentation in der UI.

Im Repo vorhanden:
- `src/quant_trader/strategies/` mit `sma_cross.py`, `momentum.py`,
  `rsi_mean_reversion.py`, `etf_rotation.py`, `loader.py`, etc.
- Docstrings in den Strategie-Klassen (englisch, eher knapp)
- KEINE separaten README-Dateien pro Strategie
- `scripts/backtest_dashboard.py` mit Tabs "Run-Form", "Read-Mode",
  "Vergleich", "Cache" (aus Slice 1.6)
- 479 Tests gruen

## Decision

### 1. README-Dateien pro Strategie

`docs/strategies/` (NEU als Verzeichnis):
- `sma_cross.md`
- `momentum.md`
- `rsi_mean_reversion.md`
- `etf_rotation.md`

Jede README auf **Deutsch** (NFR-Ux-1), mit Markdown-Formatierung,
Sections:
- Was macht die Strategie? (1-2 Absaetze)
- Wann generiert sie BUY/SELL? (signale)
- Welche Parameter hat sie? (mit Default-Werten)
- Welche Risiken hat sie? (was schlaegt fehl)
- Beispiel-Signale (textuell, nicht numerisch)

Convention: Dateiname = `StrategyLoader.registered_names()`-Eintrag.

### 2. StrategyDocLoader

`strategies/docs.py` (NEU, ~40 Zeilen):
```python
class StrategyDocLoader:
    def __init__(self, docs_dir: Path) -> None:
        self._dir = docs_dir

    def load(self, strategy_name: str) -> str | None:
        # liest docs/strategies/{strategy_name}.md
        # returnt None wenn nicht vorhanden
        ...

    def list_documented(self) -> list[str]:
        # listet alle .md files ohne .md
        ...
```

### 3. Dashboard-Integration

`scripts/backtest_dashboard.py`:
- Neuer Tab "Strategien" in `st.tabs([...])`:
  - Liste aus `StrategyLoader.default_loader().registered_names()`
  - Pro Strategie: `st.expander(f"{name} (v{version})")` mit:
    - `st.markdown(doc)` wenn README vorhanden
    - `st.warning("Keine Doku vorhanden")` + Hinweis Pfad
    - `st.dataframe(default_params.items())` mit Parameter-Liste
  - Dropdown "Strategie auswaehlen" fuer direkten Sprung
- Strukturiertes Logging: `dashboard.strategies.rendered`

### 4. Strategie-Version-Extraktion

- `StrategyLoader.default_loader()._registry[name].version`
- Oder: `cls.__init_subclass__`-Hook speichert version (nicht noetig)
- Pragmatisch: `getattr(registry[name], 'version', '1.0.0')`

## Consequences

**Positiv**
- Anfaenger koennen Strategien ohne Code-Lesen verstehen
- Doku ist versioniert im Git (mit dem Code)
- Dashboard-Integration nutzt bestehende Komponenten (Loader)
- Backward-Compat: 479 bestehende Tests unveraendert gruen
- README-Texte sind deklarativ (Markdown), kein Code-Refactor noetig

**Negativ**
- Strategie-Author muss README pflegen (kann veralten)
- Keine automatische Doku-Validierung (veraltete Strategien haengen)
- Englische Docstrings bleiben, deutsche README separat (DRY-Verlust)

**Neutral**
- Convention: Strategie-Name == Dateiname ohne `.md`
- Versions-Extraktion via ClassVar

## Alternatives Considered

- **Docstrings als Markdown-Form statt separater README**: abgelehnt,
  da Code-Konvention englisch und kurz, Doku soll deutsch + ausfuehrlich
- **Automatisches README-Generation aus Code**: zu komplex,
  YAGNI fuer Persoenlichen Use-Case
- **Wiki / externe Doku-Plattform**: abgelehnt, Git-Versionierung
  reicht, keine externe Abhaengigkeit
- **Doku nur fuer Default-Loader, nicht fuer Custom**: akzeptabel,
  User-Loader sind persoenlich
- **API-Doku (Sphinx)**: out-of-scope, kommt mit Phase 8+
- **Run-Beispiele mit echten Plots**: out-of-scope

## References

- `docs/strategies/{name}.md` (NEU, 4 files)
- `src/quant_trader/strategies/docs.py` (NEU)
- `scripts/backtest_dashboard.py` (aendern: Strategien-Tab)
- `docs/userstories/p2-strategies/strategies.md` (US-P2.8)
- `docs/prd/p2-strategies/strategy-docs.md` (Slice-PRD)
- `docs/uml/p2-strategies/strategy-docs.md` (Mermaid)
- NFR-Ux-1 (deutsche UI-Texte)
- NFR-Obs-1 (structlog)
