# PRD: Slice 3.6 - Dashboard Strategie-Vergleichsansicht

Phase:    P3 Backtest-Engine + Reports
Slice:    3.6 Dashboard Strategie-Vergleichsansicht
Status:   DRAFT  (User "ja" gilt als implizite Approval; UML auf APPROVED setzen)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Das bestehende Streamlit-Dashboard (Slices 3.3 + 3.5) um einen zweiten
Tab "Vergleich" erweitern, in dem der Trader alle registrierten
Strategien mit den Metriken ihrer juengsten Backtest-Runs nebeneinander
sieht und auf einen Blick vergleichen kann. Pro Zeile kann der Trader
direkt in den Run-Form-Tab (US-P3.9) springen, um einen neuen Backtest
mit dieser Strategie zu starten.

Live-Paper-Trading (reale Marktdaten, simulierte Orders ohne Geld) ist
explizit Phase 5 und bleibt out of scope. Die Vergleichsansicht in P3
nutzt ausschliesslich die vorhandenen Backtest-Reports.

## Scope (IN)

- `quant_trader.backtest.comparison` Sub-Package:
  - `__init__.py` mit Public-API
  - `selector.py`:
    - `latest_runs_by_strategy(loader: ReportLoader, strategy_names: list[str]) -> dict[str, RunSummary | None]`
      - Iteriert `loader.list_runs()`, gruppiert nach `strategy_name`,
        waehlt pro Strategie den Run mit dem neuesten `start`-Datum.
        Strategien ohne Reports bekommen `None`.
- `scripts/backtest_dashboard.py` Erweiterung:
  - Bestehende `st.tabs([...])` wird erweitert auf
    `st.tabs(["Run-Form", "Read-Mode", "Vergleich"])` (oder eine Liste mit
    diesen 3 Namen)
  - Neuer Tab "Vergleich":
    - `st.dataframe` mit Spalten: Strategie, Version, letzter Run
      (run_id oder "keiner"), Total Return %, Sharpe, Max Drawdown %,
      CAGR %, Anzahl Trades, Exposure %
    - Sortierung per Default: Sharpe absteigend, None ans Ende
    - Equity-Curves: fuer jede Strategie mit Report ein kleiner
      Plotly-Chart in einem 2-spaltigen Grid (`st.columns(2)`)
    - Wenn keine Strategien registriert: `st.info("Keine Strategien registriert")`
    - Wenn keine Reports vorhanden: Metriken "n/a", Equity-Bereich
      `st.info("Noch keine Backtests gelaufen")`
    - Pro Strategie mit Report: Button "Backtest starten" der auf den
      Run-Form-Tab wechselt und die Strategie vorauswaehlt
      (via `st.session_state`)
- `src/quant_trader/backtest/report/loader.py`:
  - KEINE Aenderung an der Klasse selbst, aber `list_runs()` wird vom
    neuen `latest_runs_by_strategy()` genutzt
- `src/quant_trader/backtest/__init__.py`: exportiert `latest_runs_by_strategy`
- Tests: `tests/backtest/test_comparison.py`:
  - `latest_runs_by_strategy` mit 0 Strategien: leeres Dict
  - mit 3 Strategien, 2 mit Reports, 1 ohne: Dict mit `None` fuer
    Strategie ohne Report
  - mit mehreren Reports pro Strategie: pro Strategie wird der
    juengste (nach start desc) gewaehlt
  - mit Reports ohne Strategie-Match: Strategien ohne Match bekommen `None`
  - mit Reports die gleiches start haben: deterministische Auswahl
    (z.B. lexikographisch nach run_id)
  - Sortierung der Vergleichstabelle ist deterministisch (Sharpe desc,
    None am Ende)
  - mind. 6-8 Tests mit tmp_path + Reports-Setup

## Out of Scope (verbindlich)

- Live-Paper-Trading mit echten Marktdaten (Phase 5; eigene ADR noetig)
- Auto-Backtest beim Tab-Wechsel
- Filter / Drill-Down auf Parameter-Presets
- Vergleich ueber mehrere Universen (Charts nutzen nur den letzten Run)
- Sort-/Filter-UI ueber die Vergleichstabelle hinaus (nur Default Sharpe-desc)
- Export der Vergleichstabelle als CSV
- Side-by-Side Equity-Curves auf derselben Y-Achse (mehrere Strategien
  in einem Chart) - pro Strategie eigener Mini-Chart
- BacktestEngine / Orchestrator / DashboardRunner / ReportBuilder / CLI
  aendern
- Neue Spalten in der Vergleichstabelle (z.B. Calmar, Sortino) - bleiben
  spaeteren Slices vorbehalten

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies (pandas + plotly sind bereits via ui extra da).
- Kein `print`, kein globaler State ausserhalb `st.session_state`.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, UI-Strings deutsch (NFR-Ux-1).
- Sortierung deterministisch: Python `sorted()` mit Tuple-Key
  `(-sharpe, name)` und None ans Ende.
- Tab-Wechsel: ueber `st.session_state.active_tab` + `st.tabs(key=...)`,
  kein Reload der Page.
- Per-Strategie-Mini-Chart: einfache Plotly-Linie ohne Legende,
  Title = Strategie + run_id, max 2 Charts pro Zeile (`st.columns(2)`).
- Tests deterministisch (gemockte Reports in tmp_path).

## Mapped NFRs

- NFR-Ux-1: Deutsche UI-Texte (Vergleichs-Tab, Hinweise, Buttons).

## UML-Referenz

Visualisiert in: `docs/uml/p3-backtest/comparison.md` (Status: wird auf
APPROVED gesetzt mit diesem Slice).

## Done when

- [ ] `src/quant_trader/backtest/comparison/` mit `selector.py` + `__init__.py`.
- [ ] `src/quant_trader/backtest/__init__.py` exportiert `latest_runs_by_strategy`.
- [ ] `scripts/backtest_dashboard.py` hat dritten Tab "Vergleich" mit
      Dataframe + Equity-Curves + Backstarten-Button.
- [ ] Tests in `tests/backtest/test_comparison.py` decken `latest_runs_by_strategy`
      ab.
- [ ] `make test` gruen (alle 332 alten + neuen Tests).
- [ ] `make lint` gruen.
- [ ] `uv run mypy` gruen (ohne pre-existing logging.py).
- [ ] Streamlit smoke: Modul-Load OK.
- [ ] Conventional Commit `feat(p3-backtest): slice 3.6 strategy comparison view`.
- [ ] `docs/STATE.md` aktualisiert: Slice 3.6 auf DONE, Tag `p3-backtest/3.6`.

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p3-backtest/backtest.md
cat docs/uml/p3-backtest/comparison.md
cat docs/prd/p3-backtest/comparison.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. Live-Paper-Trading
  gehoert in Phase 5.
- Wenn etwas Off-Scope auftaucht: STOP, dokumentiere, frage Nutzer.

Nach dem Coden:
- Conventional Commit mit `feat(p3-backtest): slice 3.6 strategy comparison view`.
- Commit-Body: warum selector.py separat (pure-Logik, ohne Streamlit),
  was verworfen wurde (z.B. cross-strategy Equity-Chart zugunsten
  pro-Strategie Mini-Charts).
