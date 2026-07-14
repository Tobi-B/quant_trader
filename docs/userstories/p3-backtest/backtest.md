# Phase 3 - Backtest: User Stories

Phase:    P3 Backtest-Engine + Reports
Status:   US-P3.1 bis US-P3.10 APPROVED (Slices 3.1-3.6, 2026-07-14)
          US-P3.10 (Slice 3.6) am 2026-07-14 freigegeben
Persona:  Tobias (privater Einsteiger-Trader)
Quelle:   Interview am 2026-07-14 + Erweiterung 2026-07-14 (Strategie-Vergleich)

Konvention: jede Story folgt INVEST + MoSCoW + T-Shirt-Size + Gherkin.
Nutzer-zentriert: das "Was & Warum", nicht das "Wie".

Slicing (6 Slices, genehmigt 2026-07-14; +1 in DRAFT):
- **Slice 3.1** Backtest Engine Core
- **Slice 3.2** Metrics
- **Slice 3.3** Report (Console + Plotly HTML + JSON + Streamlit, read-only)
- **Slice 3.4** Backtest CLI
- **Slice 3.5** Interaktives Backtest-Dashboard (Run-Trigger im Streamlit-UI)
- **Slice 3.6** Dashboard Strategie-Vergleichsansicht (DRAFT)

Globale Defaults (aus Interview, 2026-07-14):
- Initial Cash: 100.000 USD (per CLI ueberschreibbar)
- Fill Mode: `--fill-mode next_open` (default) oder `same_close`
- Position-Sizing: Equal-Weight (1/N bei N gleichzeitigen Positionen)
- Equity-Curve: Daily-Snapshots
- Commission/Slippage: in P3 ignoriert (kommt in P4 risk)
- Performance-Budget: 5 Jahre Daily < 30s (NFR-Perf-1)

---

## Slice 3.1 - Backtest Engine Core

### US-P3.1 - Strategie auf historische Daten backtesten

- **Als** Trader
- **moechte ich** eine Strategie auf historische Bars anwenden und Trades automatisch ausfuehren lassen,
- **damit** ich die Performance einer Strategie beurteilen kann.

- **Priority:** Must
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** eine registrierte Strategie und Bars aus dem Cache fuer den Zeitraum
  - **When** ich den Backtest starte
  - **Then** werden Signale der Strategie zu Trades: BUY -> Long-Position, SELL -> Close
  - **And** BUY wird zum Open der naechsten Bar gefillt (Default), konfigurierbar via `--fill-mode same_close`
  - **And** ohne Fill-Conflicts: bei zwei BUYS desselben Tickers hintereinander -> Position wird nur einmal aufgebaut
  - **And** ohne Fill-Konflikt: SELL ohne offene Position -> no-op (kein Crash, Warn-Log)
  - **And** die Engine loggt `backtest.start` und `backtest.complete` (Dauer, Bars, Trades)
  - **And** laeuft in unter 30s fuer 5 Jahre Daily (NFR-Perf-1)

- **Out of Scope:** Commission/Slippage (P4 risk); Limit-Orders (immer Market).

### US-P3.2 - Equal-Weight Position-Sizing

- **Als** Trader
- **moechte ich**, dass bei mehreren gleichzeitigen Positionen das Kapital gleichmaessig aufgeteilt wird,
- **damit** mein Portfolio diversifiziert ist (passt zu ETF-Rotation und Momentum top_n).

- **Priority:** Must
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** 100.000 USD Cash und 3 BUYS fuer A/B/C
  - **When** die Engine die Trades verarbeitet
  - **Then** wird A, B und C jeweils mit ca. 33.333 USD allokiert (integer Shares, Rest als Cash)
  - **And** bei SELL eines Tickers wird der Erloes wieder Cash
  - **And** eine neue BUY-Allokation nimmt die *verfuegbare* Cash-Position (RestCash nach vorherigen Allokationen)
  - **And** bei 0 USD Cash: BUY wird uebersprungen, Warn-Log `backtest.insufficient_cash`

- **Out of Scope:** Volatility-Adjustment, Risk-Parity (P4); Stop-Loss.

---

## Slice 3.2 - Metrics

### US-P3.3 - Backtest-Metriken berechnen

- **Als** Trader
- **moechte ich** nach einem Backtest die wichtigsten Kennzahlen sehen,
- **damit** ich die Strategie schnell bewerten kann.

- **Priority:** Must
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** ein abgeschlossener Backtest mit Equity-Curve und Trade-Liste
  - **When** ich die Metriken abrufe
  - **Then** erhalte ich: Total Return (%), CAGR (%), Sharpe Ratio (annualisiert, rf=0), Max Drawdown (%), Win-Rate (%), Anzahl Trades, Exposure (Anteil investiert, %)
  - **And** CAGR und Sharpe basieren auf 252 Handelstagen/Jahr
  - **And** Max Drawdown ist die groesste Spitze-zu-Tal-Periode
  - **And** bei <2 Trades: Win-Rate = None, Sharpe = None, klare Markierung in der Ausgabe
  - **And** Empty-Run (0 Trades): alle Metriken ausser Trade-Count = 0 oder NaN, klar markiert

- **Out of Scope:** Sortino, Calmar, IR (kommen spaeter bei Bedarf); Trade-PnL-Distribution.

---

## Slice 3.3 - Report (Console + Plotly + JSON + Streamlit)

### US-P3.4 - Backtest-Ergebnisse als Console-Tabelle

- **Als** Trader
- **moechte ich** die Metriken direkt in der Konsole sehen,
- **damit** ich ohne File-Output eine schnelle Einschaetzung bekomme.

- **Priority:** Must
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** ein abgeschlossener Backtest
  - **When** ich den Run im Terminal anzeige
  - **Then** sehe ich eine formatierte Tabelle mit allen Metriken aus US-P3.3
  - **And** darunter eine zweite Tabelle mit den Top-10 Trades (Einstieg, Ausstieg, P&L)
  - **And** Ausgabe auf Deutsch, fixed-width Spalten, deterministisch (testbar)
  - **And** bei Empty-Run: Tabelle zeigt "keine Trades" ohne Crash

- **Out of Scope:** CSV-Export der Trades; Sort/Filter-UI (kommt mit Streamlit).

### US-P3.5 - Equity-Curve als interaktives Plotly-HTML

- **Als** Trader
- **moechte ich** die Equity-Curve als interaktive HTML-Datei oeffnen koennen,
- **damit** ich im Browser rein- und rauszoomen und einzelne Punkte inspizieren kann.

- **Priority:** Should
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** ein Backtest mit Equity-Curve (>=1 Snapshot)
  - **When** ich den Report generiere
  - **Then** wird `reports/<run-id>/equity_curve.html` erzeugt
  - **And** die HTML enthaelt eine Plotly-Figure mit X=Date, Y=Equity
  - **And** Hover zeigt Datum + Equity + Position-Snapshot (Cash, gehaltene Ticker)
  - **And** bei Empty-Run: HTML enthaelt leere Figure mit Hinweis "Keine Trades"
  - **And** Datei ist self-contained (Plotly-JS inline oder CDN)

- **Out of Scope:** Drawdown-Chart in HTML (kommt spaeter optional); Vergleichs-Overlay mehrerer Runs.

### US-P3.6 - Backtest als JSON exportieren

- **Als** Trader
- **moechte ich** die Backtest-Ergebnisse als JSON speichern,
- **damit** ich sie programmatisch weiterverarbeiten oder mit anderen Tools analysieren kann.

- **Priority:** Should
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** ein abgeschlossener Backtest
  - **When** ich den Run abschliesse
  - **Then** wird `reports/<run-id>/result.json` erzeugt mit: strategy_name, params, start, end, fill_mode, initial_cash, final_equity, alle Metriken, equity_curve (Liste von {date, equity, cash, positions}), trades (Liste von {ticker, entry_date, entry_price, exit_date, exit_price, pnl, pnl_pct})
  - **And** Schema ist stabil (typed; floats als Number, dates als ISO-String)
  - **And** Pfad wird in `backtest.complete` Log geloggt

- **Out of Scope:** Parquet-Export; CSV-Export.

### US-P3.7 - Streamlit-Dashboard fuer Backtest-Vergleich

- **Als** Trader
- **moechte ich** im Browser durch vergangene Backtests browsen und Strategien vergleichen,
- **damit** ich ohne Command-Line-Aufrufe die Ergebnisse erkunden kann.

- **Priority:** Should
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** das Streamlit-Extra ist installiert (`uv sync --extra ui`)
  - **When** ich `streamlit run scripts/backtest_dashboard.py` starte
  - **Then** oeffnet sich ein Browser-Fenster mit Sidebar (Strategie-Selector, Run-Selector)
  - **And** Hauptbereich zeigt: Equity-Curve (Plotly), Metriken-Tabelle, Drawdown-Indicator, Top-Trades-Tabelle
  - **And** ich kann zwischen verschiedenen Runs wechseln ohne Neustart
  - **And** wenn `reports/` leer ist: freundlicher Hinweis "Noch keine Backtests gelaufen"
  - **And** nur lesend (kein Button "Run Backtest" in der UI)

- **Out of Scope:** Parameter-Sweep-UI; Run-Trigger-Button; User-Login.

---

## Slice 3.4 - Backtest CLI

### US-P3.8 - Backtest ueber CLI starten

- **Als** Trader
- **moechte ich** einen Backtest per CLI-Aufruf starten koennen,
- **damit** ich reproduzierbar dieselben Runs wiederholen kann.

- **Priority:** Must
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** ein gueltiger CLI-Aufruf
  - **When** ich `python -m quant_trader.backtest run --strategy sma_cross --ticker SPY --start 2020-01-01 --end 2024-12-31` aufrufe
  - **Then** laeuft der Backtest und produziert Console-Output (Metriken + Top-Trades, US-P3.4)
  - **And** ohne `--no-report`: HTML (US-P3.5) + JSON (US-P3.6) werden unter `reports/<run-id>/` geschrieben
  - **And** `--fill-mode next_open|same_close` waehlt Fill-Mode (default next_open)
  - **And** `--initial-cash 50000` ueberschreibt Default
  - **And** `--no-report` ueberspringt File-Output
  - **And** Exit 0 bei Erfolg, 1 bei Fehler (Strategy/Universe/Cache fehlt)
  - **And** `python -m quant_trader.backtest list` zeigt alle Backtests aus `reports/`

- **Out of Scope:** Scheduler/Cron-Integration; Multi-Backtest-Batch in einem CLI-Call.

---

## Slice 3.5 - Interaktives Backtest-Dashboard (Run-Trigger)

Erweitert das in US-P3.7 definierte Streamlit-Dashboard (zunaechst read-only)
um einen Backtest-Trigger. Fill-Mode, Initial-Cash und Granularity bleiben
bewusst ausserhalb des UI (CLI-/YAML-Defaults), damit der Scope klein bleibt.

### US-P3.9 - Backtest aus dem Dashboard starten

- **Als** Trader
- **moechte ich** im Dashboard Strategie, Ticker/Universe und Zeitraum auswaehlen
  und den Backtest per Knopfdruck starten und das Ergebnis direkt darunter sehen,
- **damit** ich Backtests ohne CLI-Aufruf durchfuehren und sofort visuell bewerten kann.

- **Priority:** Should
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** das Streamlit-Extra ist installiert (`uv sync --extra ui`) und ich habe das Dashboard geoeffnet
  - **When** ich in der Sidebar eine registrierte Strategie (Dropdown aus der Registry), einen Ticker (Freitext) oder ein Universe-Preset (Dropdown aus `config/universe_presets.yaml`), Start- und Enddatum (Date-Input) waehle und auf "Backtest starten" klicke
  - **Then** startet die BacktestEngine aus Slice 3.1 mit diesen Parametern (Fill-Mode = `next_open`, Initial-Cash = 100.000 USD, Granularity = `daily` als Default; keine UI-Felder dafuer)
  - **And** waehrend des Laufs sehe ich einen Progress-Spinner mit Live-Log-Stream (structlog)
  - **And** nach Abschluss erscheinen Metriken-Tabelle, Equity-Curve (Plotly) und Top-Trades-Tabelle direkt unter dem Formular im selben Tab
  - **And** der Run wird persistent unter `reports/<run-id>/` abgelegt (result.json + equity_curve.html + console-Log) und ist danach im Read-Mode (US-P3.7) aufrufbar
  - **And** bei Fehlern (Cache fehlt, ungueltiges Datum, unbekannter Ticker, leere Strategie-Liste): klare deutsche Fehlermeldung in der UI, kein Streamlit-Crash
  - **And** die UI blockiert waehrend des Runs (kein Doppel-Klick auf "Start" moeglich, Button disabled)

- **Out of Scope:** UI-Felder fuer Fill-Mode, Initial-Cash, Granularity (CLI/YAML-Defaults); Non-Blocking / Background-Jobs; Cancel-Button; Parameter-Presets / Sweeps; Live-Trading-Trigger (Phase 5); Multi-Backtest-Batch in einem Run.

---

## Slice 3.6 - Dashboard Strategie-Vergleichsansicht (DRAFT)

Erweitert das Streamlit-Dashboard um einen zweiten Tab "Vergleich", in
dem der Trader alle registrierten Strategien auf einen Blick sieht und
anhand der jeweils aktuellsten Backtest-Runs vergleichen kann. Fokus
ist der Strategie-Vergleich (nicht die Run-Geschichte), damit der Trader
schnell entscheiden kann, welche Strategie weiter verfolgt werden soll.

Live-Paper-Trading (reale Marktdaten, simulierte Orders ohne Geld) ist
explizit Phase 5 und bleibt out of scope. Die Vergleichsansicht in P3
nutzt ausschliesslich die vorhandenen Backtest-Reports.

### US-P3.10 - Registrierte Strategien im Dashboard vergleichen

- **Als** Trader
- **moechte ich** im Dashboard einen Tab "Vergleich" sehen, in dem alle
  registrierten Strategien mit ihrem letzten Backtest-Ergebnis
  (Metriken + Equity-Curve) nebeneinander aufgelistet sind,
- **damit** ich auf einen Blick erkennen kann, welche Strategie
  aktuell am besten performt, ohne manuell durch Reports zu navigieren.

- **Priority:** Should
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** das Streamlit-Extra ist installiert und ich habe das Dashboard geoeffnet
  - **When** ich auf den Tab "Vergleich" wechsle
  - **Then** sehe ich eine Tabelle mit einer Zeile pro registrierter Strategie (aus `StrategyLoader.registered_names()`) und Spalten: Strategie, Version, letzter Run (run_id oder "keiner"), Total Return %, Sharpe, Max Drawdown %, CAGR %, Anzahl Trades, Exposure %
  - **And** fuer jede Strategie mit vorhandenem Backtest-Report wird der juengste `RunSummary` (nach `start` desc) verwendet; Strategien ohne Report zeigen in den Metrik-Spalten ein "n/a"
  - **And** ueber der Tabelle sehe ich eine Auswahl an Equity-Curves: jede Strategie mit Report wird in einem eigenen kleinen Plotly-Chart (gestapelt oder Gitter) gezeigt
  - **And** Sortierung der Tabelle ist per Default nach Sharpe absteigend (None-Werte ans Ende)
  - **And** ein "Backtest starten"-Button pro Zeile oeffnet den Run-Form-Tab (US-P3.9) mit vorausgewaehlter Strategie (Tab-Wechsel, nicht neuer Run)
  - **And** wenn keine Strategien registriert sind: Hinweis "Keine Strategien registriert" statt Crash
  - **And** wenn keine Reports vorhanden sind, aber Strategien registriert: Tabelle zeigt Metriken als "n/a", Equity-Chart-Bereich zeigt Hinweis "Noch keine Backtests gelaufen"

- **Out of Scope:** Live-Paper-Trading mit echten Marktdaten (Phase 5); On-the-fly-Backtest fuer den Vergleich (kein Auto-Run beim Tab-Wechsel); Filter oder Drill-Down auf Parameter-Presets; Vergleich ueber mehrere Universen (Charts nur Default-Config, falls vorhanden); Sort/Filter-UI ueber die Vergleichstabelle hinaus; Export der Vergleichstabelle als CSV.

---

## Mapped NFRs (siehe docs/requirements/nfrs.md)

| Story    | NFR-IDs                                                |
|----------|---------------------------------------------------------|
| US-P3.1  | NFR-Perf-1 (<30s), NFR-Obs-1 (Logs), NFR-Data-1 (Cache) |
| US-P3.2  | NFR-Ux-1 (klare Logs: insufficient_cash)               |
| US-P3.3  | NFR-Perf-1 (schnelle Metrik-Berechnung)                |
| US-P3.4  | NFR-Ux-1 (deutsche Texte, klar)                        |
| US-P3.5  | NFR-Data-2 (Adj. Close)                                |
| US-P3.6  | NFR-Data-2                                              |
| US-P3.7  | NFR-Ux-1                                               |
| US-P3.8  | NFR-Ux-1, NFR-Obs-1                                   |
| US-P3.9  | NFR-Ux-1, NFR-Obs-1, NFR-Perf-1, NFR-Data-1           |
| US-P3.10 | NFR-Ux-1 (deutsche UI-Texte)                            |

---

## Definition of Done (alle Stories)

- [ ] BacktestEngine + Portfolio + Position-Sizer implementiert (3.1)
- [ ] Metrics: Sharpe, CAGR, MDD, Win-Rate, Exposure (3.2)
- [ ] Report: ConsoleFormatter, PlotlyExporter, JsonExporter, Streamlit-Dashboard (3.3)
- [ ] CLI `python -m quant_trader.backtest {run,list}` (3.4)
- [ ] Dashboard: Run-Trigger mit Engine-Wiring, Progress, Fehler-Handling (3.5)
- [ ] Dashboard: Strategie-Vergleichsansicht (registrierte Strategien + letzte Runs) (3.6)
- [ ] Tests fuer Engine-Korrektheit, deterministische Metriken, Report-Roundtrip, Dashboard-Trigger, Vergleichsansicht
- [ ] `make test`, `make lint`, `make smoke` gruen
- [ ] Conventional Commits, einer pro Slice
- [ ] `docs/STATE.md` aktualisiert, Tag `p3-backtest` gesetzt
- [ ] UML-Diagramme (Structure + Flow + Sequence + State Machine) APPROVED