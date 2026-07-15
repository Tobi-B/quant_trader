# PRD: Slice 2.6 - Strategy Documentation Viewer

Phase:    P2 Strategien (Erweiterung)
Slice:    2.6 Strategy Documentation Viewer
Status:   DRAFT  (User "README pro Strategie + Dashboard-Anzeige" gilt als implizite Approval; UML auf APPROVED setzen)
Author:   opencode
Created:  2026-07-15
Updated:  2026-07-15

## Goal

Jede registrierte Strategie bekommt eine ausfuehrliche
Markdown-README (deutsch), die ihre Funktionsweise, Parameter und
Risiken erklaert. Diese READMEs werden im Streamlit-Dashboard in
einem neuen "Strategien"-Tab zugaenglich gemacht, damit der Trader
als Anfaenger ohne Code-Lesen versteht, was jede Strategie macht.

## Scope (IN)

- `docs/strategies/` (NEU als Verzeichnis):
  - `sma_cross.md` mit sections: Was?, Wann BUY/SELL?, Parameter, Risiken
  - `momentum.md` (gleich strukturiert)
  - `rsi_mean_reversion.md` (gleich strukturiert)
  - `etf_rotation.md` (gleich strukturiert)
  - Convention: `docs/strategies/<registered_name>.md`, also
    `sma_cross` Strategie -> `sma_cross.md`
- `src/quant_trader/strategies/docs.py` (NEU, ~40 Zeilen):
  - `StrategyDocLoader(docs_dir: Path)` Klasse
  - `load(strategy_name: str) -> str | None`: liest MD-File, returnt
    None wenn nicht vorhanden
  - `list_documented() -> list[str]`: alle dokumentierten Strategien
- `src/quant_trader/strategies/__init__.py` (aendern): export
  `StrategyDocLoader`
- `src/quant_trader/core/config.py` (aendern): Settings-Erweiterung
  - `strategy_docs_dir: Path = Path("./docs/strategies")`
- `scripts/backtest_dashboard.py` (aendern):
  - Neuer Tab "Strategien" in `st.tabs([...])`
  - Liste `StrategyLoader.default_loader().registered_names()` + Version
  - Pro Strategie `st.expander(...)` mit:
    - `st.markdown(doc)` wenn vorhanden
    - `st.warning("Keine Doku vorhanden fuer X. Bitte erstelle docs/strategies/X.md")`
    - `st.dataframe(default_params.items(), column_names=("Parameter", "Default"))`
  - Dropdown "Springe zu Strategie" fuer direkten Sprung
  - Strukturiertes Logging: `dashboard.strategies.rendered`
- Tests: `tests/strategies/test_strategy_docs.py`, `tests/strategies/test_docs_loader.py` (NEU, gesamt mind. 8 Tests):
  - `test_docs.py` (mind. 5 Tests):
    - `test_loader_loads_existing_md_file`
    - `test_loader_returns_none_for_missing_file`
    - `test_loader_lists_documented_strategies`
    - `test_loader_handles_empty_docs_dir`
    - `test_loader_reads_empty_md_file_as_empty_string`
  - `test_dashboard_strategies_tab.py` (oder im test_backtest_dashboard):
    - `test_dashboard_imports_strategy_docs_loader`
    - `test_dashboard_has_strategies_tab_in_tabs_list`
  - **Pragmatisch**: meist nur Loader-Tests; Dashboard-Tab-Tests
    sind schwer (Streamlit) - stattdessen Verify via AST-Parsing oder
    simple Import-Test
- Markdown-Inhalte der 4 Strategien:
  - Mindestens 5 Sections (Was, Wann-Signal, Parameter, Risiken,
    Beispiel). Inhaltlich korrekt (basierend auf Docstrings + Logik
    der jeweiligen Strategie).
  - Deutsche Texte, Markdown-Formatierung
  - Beispiel: `sma_cross.md`:
    ```
    # SMA-Cross (Simple Moving Average Crossover)
    
    ## Was?
    Trivial-Trendfolge: Wenn der schnelle SMA den langsamen SMA
    von unten nach oben kreuzt -> BUY. Umgekehrt -> SELL.
    
    ## Wann BUY/SELL?
    **BUY**: `sma_fast` (default 20) kreuzt `sma_slow` (default 50)
    von unten nach oben.
    
    ## Parameter
    | Parameter | Default | Bedeutung |
    |-----------|---------|-----------|
    | fast | 20 | Fenster fuer schnellen SMA |
    | slow | 50 | Fenster fuer langsamen SMA |
    
    ## Risiken
    - **Whipsaws** in Seitwaerts-Maerkten (false signals)
    - Lag: reagiert verzoegert auf echte Trend-Bruche
    - Kein Risk-Management (kein Stop-Loss out-of-the-box)
    ```
- Doku-Updates:
  - `docs/STATE.md`: Slice 2.6 auf DONE, Tag `p2-strategies/2.6`
  - `docs/adr/0016-strategy-documentation.md`: Status `proposed` -> `accepted`

## Out of Scope (verbindlich)

- Englische README-Variante (Doku ist auf Deutsch)
- Automatische README-Generation aus Code
- Live-Edit der Doku im Dashboard
- API-Doku fuer `StrategyBase` (Sphinx, out-of-scope)
- Strategie-Performance-Tests (Slice 3.x Backtests)
- Backtest-Beispiele mit echten Plots
- Vergleich der Strategien (Slice 3.6 hat das bereits)
- README-Versionierung ueber Git-Tags
- Validierung der README (Auto-Check ob Parameter-Stub mit Code uebereinstimmt)

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies.
- Kein `print`, kein globaler State.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, README deutsch, Dashboard-UI deutsch.
- **KRITISCH**: alle 479 bestehenden Tests unveraendert gruen
- README-Dateien MINDESTENS 5 Sections (Was, Wann-Signal, Parameter,
  Risiken, Beispiel)
- Convention: `docs/strategies/<strategy-name>.md` (Filename =
  registered_name, exakt)

## Mapped NFRs

- NFR-Ux-1 (deutsche UI-Texte, deutsche READMEs)
- NFR-Obs-1 (structlog fuer Dashboard-Render-Events)

## UML-Referenz

Visualisiert in: `docs/uml/p2-strategies/strategy-docs.md` (Status: wird
auf APPROVED gesetzt mit diesem Slice).

## Done when

- [ ] `docs/strategies/{sma_cross,momentum,rsi_mean_reversion,etf_rotation}.md`
      mit jeweils mind. 5 Sections, deutsche Texte
- [ ] `src/quant_trader/strategies/docs.py` mit `StrategyDocLoader`
- [ ] `Settings.strategy_docs_dir: Path = Path("./docs/strategies")`
- [ ] `scripts/backtest_dashboard.py` mit Strategien-Tab
- [ ] Tests in `tests/strategies/` mit gesamt mind. 8 Tests
- [ ] `make test` gruen (alle 479 alten + neuen Tests)
- [ ] `make lint` gruen
- [ ] `mypy --strict` gruen (0 errors)
- [ ] ADR-0016 auf "accepted"
- [ ] Conventional Commit `feat(p2-strategies): slice 2.6 strategy docs`
- [ ] `docs/STATE.md` aktualisiert: Slice 2.6 auf DONE, Tag
      `p2-strategies/2.6`

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p2-strategies/strategies.md
cat docs/adr/0016-strategy-documentation.md
cat docs/uml/p2-strategies/strategy-docs.md
cat docs/prd/p2-strategies/strategy-docs.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. API-Doku, Sphinx, etc.
  sind out.
- **KRITISCH**: alle 479 bestehenden Tests unveraendert gruen.

Nach dem Coden:
- Conventional Commit mit `feat(p2-strategies): slice 2.6 strategy docs`.
- Commit-Body: warum separate README-Files (statt Docstrings), warum
  Dashboard-Integration (StrategyLoader als Single-Source-of-Truth).
