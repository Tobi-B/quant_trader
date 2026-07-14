# QuantTrader - Session Resume

> **Anker fuer Session-Resume.** Diese Datei macht den aktuellen Projektzustand
> in einem einzigen Blick lesbar. Vor jedem Coden: diese Datei lesen + dann PRD/User-Story/UML.

## Schnappschuss

| Feld                  | Wert                                                |
|-----------------------|------------------------------------------------------|
| Datum                 | 2026-07-14                                          |
| Letzter Commit (main) | TBD (slice 7.1 commit)                              |
| Branch                | `main` (clean, alle Aenderungen gepusht)           |
| Tests                 | 440/440 gruen (434 + 6 neue)                        |
| Lint + Format         | gruen                                               |
| Aktive Phase          | P7 Docker-Deployment                                |
| Aktiver Slice         | Slice 7.1 (Docker-Deployment + CI/CD) - DONE        |
| Open Decision         | - (Projekt komplett deployable)                     |

## Phasen-Tags (chronologisch)

| Tag            | Phase                  | Datum       | Status    |
|----------------|------------------------|-------------|-----------|
| `p0`           | Harness + Bootstrap    | 2026-07-08  | abgeschlossen |
| `p1-universe`  | Universe Loader        | 2026-07-08  | abgeschlossen |
| `p1-data`      | DataProvider + Cache   | 2026-07-08  | abgeschlossen |
| `p1-intraday`  | Intraday Support       | 2026-07-08  | abgeschlossen |
| `p2-strategies/2.1` | Strategy Framework | 2026-07-10 | abgeschlossen |
| `p2-strategies/2.2` | Trend (SMA + Momentum) | 2026-07-10 | abgeschlossen |
| `p2-strategies/2.3` | Mean-Reversion (RSI) | 2026-07-10 | abgeschlossen |
| `p2-strategies/2.4` | ETF-Rotation        | 2026-07-10 | abgeschlossen |
| `p2-strategies/2.5` | Signal-Runner CLI   | 2026-07-14 | abgeschlossen |
| `p3-backtest/3.1`   | Backtest Engine Core | 2026-07-14 | abgeschlossen |
| `p3-backtest/3.2`   | Metrics             | 2026-07-14 | abgeschlossen |
| `p3-backtest/3.3`   | Report (Console + Plotly + JSON + Streamlit) | 2026-07-14 | abgeschlossen |
| `p3-backtest/3.4`   | Backtest CLI | 2026-07-14 | abgeschlossen |
| `p3-backtest/3.5`   | Dashboard Run-Trigger | 2026-07-14 | abgeschlossen |
| `p3-backtest/3.6`   | Strategie-Vergleichsansicht | 2026-07-14 | abgeschlossen |
| `p1-data/1.5`        | Financial Modelling Prep Provider als Primary | 2026-07-14 | abgeschlossen |
| `p4-risk/4.1`        | Risk-Engine (Commission + Slippage + Stop-Loss) | 2026-07-14 | abgeschlossen |
| `p5-live/5.1`        | Broker Interface + Mock + Order (Foundation) | 2026-07-14 | abgeschlossen |
| `p5-live/5.2`        | Live-Loop + Trade-Journal + Live-CLI | 2026-07-14 | abgeschlossen |
| `p5-live/5.3`        | Auto-Reconnect + Tageszusammenfassung + Credentials | 2026-07-14 | abgeschlossen |
| `p7-ops/7.1`         | Docker-Deployment (Multi-Stage + Compose + CI/CD)   | 2026-07-14 | abgeschlossen |

## Was steht (verifiziert)

- **CLI** `python -m quant_trader.universe {load,list}` und
  `python -m quant_trader.data TICKER [--universe ...] [--granularity daily|60m|15m]`
- **Provider-Chain**: Financial Modelling Prep (FMP) -> YFinance -> StockData.org -> AlphaVantage
- **FMP Provider (Slice 1.5 DONE)**: Daily, 60m und 15m ueber die FMP-API; Rate-Limits und Provider-Fehler fallen transparent auf die bestehende Kette zurueck.
- **Cache**: Parquet unter `data/raw/{daily,60m,15m}/<TICKER>.parquet`, idempotent
- **Universe YAML**: `config/universe_presets.yaml` (sp500/dax40/etfs)
- **.env (gitignored)**: API-Keys bleiben ausserhalb des Repos; der FMP-Key wird ueber `FINANCIAL_MODELLING_PREP_KEY` gelesen.
- **CLI-Smoke** 6 Schritte demonstriert in `Sprint-Demo` oben.
- **P2 Doku APPROVED** (22e6300): US-P2.1+US-P2.2 freigegeben, framework.md
  + runner.md UMLs APPROVED, Slice 2.1 PRD erstellt.
- **Architecture-Doku** (53ab219): `docs/architecture.md` mit Layered-Overview,
  Module-Tabelle, Datenfluss. `docs/adr/` mit 11 ADRs (0001-0011).
- **Slice 2.1 DONE** (0639c7e): Strategy Framework implementiert. 36 neue Tests
  (test_types, test_base, test_loader). 120/120 gruen. Lint + Format gruen.
  Registry-Pattern + ABC-Design via ADR 0007/0008 dokumentiert.
- **Slice 2.2 DONE** (399c678): SmaCrossStrategy + MomentumStrategy
  implementiert. Framework-Erweiterung: `ticker` als Konstruktor-Param.
  22 neue Tests (test_sma_cross 9, test_momentum 11). 142/142 gruen.
- **Slice 2.3 DONE** (bf1f9a9): RsiMeanReversionStrategy (simple-average RSI,
  Cutler-Variante). 11 neue Tests. 153/153 gruen.
- **Slice 2.4 IN_PROGRESS**: US-P2.6 + rotation-UML APPROVED
  (2026-07-10). Slice-PRD `docs/prd/p2-strategies/etf-rotation.md`
  erstellt. EtfRotationStrategy folgt.
- **Slice 2.4 DONE** (ed3af58): EtfRotationStrategy (Top-N Momentum,
  defensive Cash-Branch bei non-positive Returns). 15 neue Tests
  (default / warmup / Param-Validierung / Warmup-Gate / Top-N-Buy /
  Holder-dropped-Sell / Defensive-Cash / Same-Month-NoSignal /
  Rebalance-Log / Loader-Integration). 168/168 gruen.
- **Slice 2.5 DONE** (380d752): SignalRunner + SignalFormatter + CLI
  (`python -m quant_trader.strategies {run,list}`). Auto-detect
  Single-vs Multi-Ticker via `isinstance`. CLI-Subcommands `run` mit
  `--strategy/--ticker/--universe/--granularity/--start/--end/--limit`,
  `list` mit registrierten Strategien. 17 neue Tests (Formatter
  empty/single/limit, Single-Ticker Happy/Missing/Ohne-Ticker,
  Multi-Ticker Params+Preset, Unknown-Strategy, Parser-Structure,
  CLI rc-Codes + List-Output). 185/185 gruen. ruff + mypy --strict
  clean. Smoke: `python -m quant_trader.strategies list` liefert 4
  Strategien; `run --strategy unknown` -> Exit 1 mit Available-Liste;
  `run --strategy sma_cross --ticker ZZZZ` -> Exit 1 mit
  Cache-Hint.
- **Slice 3.1 DONE**: BacktestEngine + Portfolio + PositionSizer +
  FillSimulator implementiert. `BacktestConfig`/`BacktestResult`/
  `Trade`/`EquitySnapshot` als frozen Dataclasses. Pending-Fill-Queue
  fuer NEXT_OPEN ohne Look-Ahead. EqualWeightSizer mit 1/(n+1)
  Verteilung. 42 neue Tests (sizer 9, portfolio 12, fill 3, engine 18).
  227/227 gruen. ruff + mypy clean (ausser pre-existing
  `core/logging.py` Issue, out of scope).
- **Slice 3.2 DONE**: MetricsCalculator + EquityCurveStats + TradeStats
  implementiert. Total Return %, CAGR %, Sharpe Ratio (annualisiert,
  rf=0, 252 Tage), Max Drawdown %, Win-Rate %, Exposure %, n_trades.
  CAGR via math.pow (mypy-safe). 34 neue Tests (EquityCurveStats 17,
  TradeStats 6, MetricsCalculator 9, Integration 1). 261/261 gruen.
  ruff + mypy clean.
- **Slice 3.3 DONE**: Report-Sub-Package mit ConsoleFormatter (fixed-width
  deutsche Tabellen), PlotlyExporter (self-contained HTML via CDN),
  JsonExporter (stabile Schema v1 mit ISO-Dates), ReportLoader
  (liest result.json aus reports/<run_id>/), ReportBuilder
  (orchestriert alle drei). `scripts/backtest_dashboard.py` mit
  Streamlit-Read-Mode (Sidebar-Selectors, Plotly-Chart, KPI-Metriken,
  Trade-Tabelle). 33 neue Tests (console 10, plotly 4, json 7, loader
  7, builder 5). 294/294 gruen. ruff + mypy clean. Dashboard-Script
  manuell smoke-getestet (Modul-Load OK).
- **Slice 3.4 DONE**: Backtest CLI (`python -m quant_trader.backtest {run,list}`)
  + `BacktestOrchestrator` (DI-Pattern: cache, loader, report_builder,
  reports_dir). `__main__.py` Entry-Point, `scripts/run_backtest.py`
  delegiert. Error-Hierarchie erweitert (UnknownStrategyError mit
  `name`+`available`, CacheMissingError mit `ticker`+`path`,
  InvalidParamsError). CLI strukturiert mit Subcommands, deutsche
  Fehlermeldungen auf stderr, Exit 0/1/2. 25 neue Tests (Parser 8,
  CLI-Run 9, CLI-List 2, Orchestrator-Direct 5, plus negative-path
  Multi-Ticker ohne universe, invalid date, unknown strategy, missing
  cache, single-ticker ohne ticker). 319/319 gruen. ruff + mypy clean
  (ausser pre-existing core/logging.py). Smoke: `--help`, `run --help`,
  `list --help`, `list --reports-dir`, unknown-strategy mit
  Available-Liste OK.
- **Slice 3.5 DONE**: Dashboard Run-Trigger (`DashboardRunner` +
  Streamlit-Tabs "Run-Form"/"Read-Mode"). `DashboardRunner` ist pure
  Library-Code (kein Streamlit-Import) mit DI auf Orchestrator + Loader
  + Presets; `run_request(strategy, ticker, universe, start, end) ->
  (run_id, BacktestResult)` validiert Strategie, resolvet Universe-Preset
  (uppercase Ticker), generiert `run_id` via `datetime.now().strftime(...)`
  und delegiert an Orchestrator mit Defaults `FillMode.NEXT_OPEN`,
  `Granularity.DAILY`, `initial_cash=100_000.0`. Strukturiertes Logging
  `backtest.dashboard.start`/`complete`/`unknown_strategy`. Errors
  (UnknownStrategy, CacheMissing, InvalidParams, BacktestError) reicht
  der Streamlit-Layer ab und zeigt deutsche `st.error(...)`-Texte.
  `scripts/backtest_dashboard.py` nutzt jetzt `st.tabs([...])`: Tab
  "Run-Form" mit Strategie/Universe-Selectbox + Custom-Ticker + Date-Inputs,
  `disabled`-Button waehrend Run, Spinner + Result-Anzeige (KPIs,
  Equity-Curve, Trades) direkt darunter; Tab "Read-Mode" bleibt aus 3.3.
  13 neue Tests (Happy-Path + Unknown + Empty-Ticker + Universe-Resolution
  + Uppercase + Run-ID-Format + Cache-Propagation + Logging-Events).
  332/332 gruen. ruff + mypy clean (ausser pre-existing core/logging.py).
  Smoke: `importlib.util`-Load des Scripts ohne Streamlit-Import OK.
- **Slice 3.6 DONE**: Strategie-Vergleichsansicht als dritter Streamlit-Tab
  implementiert. `latest_runs_by_strategy` waehlt pro registrierter Strategie
  den juengsten Report deterministisch nach Startdatum und Run-ID.
  `ComparisonRow` + `ComparisonTable` bauen und sortieren die Vergleichszeilen
  (Sharpe absteigend, fehlende Werte zuletzt). Das Dashboard zeigt deutsche
  Metrik-Spalten mit `n/a`, Equity-Mini-Charts im 2-Spalten-Grid und pro
  Strategie einen Sprung ins vorausgefuellte Run-Form. Strukturiertes Logging
  via `backtest.comparison.render`. 8 neue Tests, 340/340 gruen. Ruff Check +
  Format gruen; mypy nur mit den zwei bekannten `core/logging.py`-Fehlern.
  Dashboard-Modul-Smoke OK.
- **Slice 4.1 DONE**: Risk-Engine (Commission + Slippage + Stop-Loss)
  implementiert. `BacktestConfig` um `commission_per_trade`,
  `commission_per_share`, `slippage_pct`, `stop_loss_pct` erweitert
  (Defaults 0.0 / None fuer Backward-Compat). `FillSimulator.resolve`
  applied Slippage symmetrisch auf BUY (+pct) und SELL (-pct) an den
  Fill-Preis. `BacktestEngine._apply_fill` berechnet
  `commission = max(per_trade, qty * per_share)` und bucht es auf
  Cash; `Trade.pnl` beruecksichtigt Entry- und Exit-Commission
  automatisch. `_check_stop_losses` laeuft pro Bar **vor**
  `strategy.on_bar` (auch in Multi-Ticker-Modus, alphabetisch
  sortiert) und enqueu einen internen `Signal(action=SELL,
  reason="stop_loss")` ueber die normale Fill-Pipeline. Strukturiertes
  Logging `backtest.stop_loss` (WARNING, mit `ticker`/`entry_price`/
  `trigger_price`/`stop_loss_pct`) und `backtest.complete` jetzt mit
  `total_commission` und `stop_loss_count`. 23 neue Tests
  (Commission-Berechnung 5, Commission-Buchung 4, Slippage 5,
  Stop-Loss 5, Integration 4). 378/378 gruen. ruff + mypy clean
  (inkl. `core/logging.py`). ADR-0010 Status `proposed` -> `accepted`.
- **Slice 5.1 DONE**: Broker Interface + Mock + Order (Foundation).
  `src/quant_trader/live/` als neues Sub-Package mit `Order`/`Position`
  (frozen dataclasses), `OrderStatus`/`OrderType` (StrEnum), Protocol
  `BrokerClient`, `MockBroker` (deterministisch, synchron SUBMITTED ->
  FILLED; REJECTED bei qty<=0), `IBKRBroker` (Stub mit
  `NotImplementedError` fuer Slice 5.2), `build_broker(settings)`
  Factory (live_enabled -> IBKR vs Mock). `client_order_id` als UUID
  (NFR-Rel-3 Idempotenz). ib_insync nur in `ibkr.py` mit
  try/except ImportError -> `SystemExit`; Factory und `__init__.py`
  lazy-importieren IBKRBroker, sodass CI ohne `live` extra lauffaehig
  bleibt. Strukturiertes Logging `broker.order_placed`/
  `broker.order_filled`/`broker.order_rejected`/
  `broker.order_cancelled`. `Settings` erweitert um `live_enabled`,
  `ibkr_host`, `ibkr_port`, `ibkr_client_id`, `mock_fill_price`
  (alle mit Defaults; Backward-Compat gewahrt). 16 neue Tests
  (MockBroker 12 inkl. Cancel-Pending/Filled/Unknown + State,
  Factory 4). 394/394 gruen. ruff + mypy clean. ADR-0011 Status
  `proposed` -> `accepted`.
- **Slice 5.2 DONE**: Async `LiveLoop` verbindet Broker und Realtime-Bar-Quelle,
  verarbeitet Single-Ticker-Strategien und persistiert gefuellte BUY-/SELL-Zyklen
  ueber `TradeJournal` in SQLite. `client_order_id` ist UNIQUE, WAL-Modus und
  Run-ID-Index sind aktiv. `MockBarSource._inject()` liefert deterministische
  Queue-Bars; `IBKRBarSource` nutzt `reqRealTimeBars()`-Events. Die Live-CLI
  `python -m quant_trader.live {run,list}` unterstuetzt Broker-Auswahl und
  Laufzeiten in Sekunden, Minuten oder Stunden. `IBKRBroker` implementiert
  Connect/Disconnect, Market-Orders, Positionen und Cancellation. 23 neue Tests
  (Journal 8, Bars 5, Loop 5, CLI 5). 417/417 gruen; Ruff Check + Format und
  mypy --strict clean. ADR-0012 akzeptiert; Tag `p5-live/5.2`.
- **Phase 5 DONE**: Slice 5.3 schliesst Phase 5 (Live-Trading) ab.
  Auto-Reconnect (NFR-Rel-2): `LiveLoop._monitor_connection()` laeuft als
  Background-Task, prueft alle 5s `broker.is_connected()`, und ruft
  `_reconnect_with_backoff()` mit Exponential-Backoff (1s -> 30s cap, 10
  Attempts). Nach erfolgreichem Reconnect werden alle subscribed Ticker via
  `_restore_subscriptions()` re-subscribed und Positionen via
  `broker.get_positions()` re-synced. `MockBroker.is_connected()` bleibt
  immer True (kein Reconnect noetig fuer Tests). Tageszusammenfassung
  (NFR-Obs-2): `DailySummary` (frozen dataclass) + `DailySummaryFormatter`
  (fixed-width deutsche Tabelle mit Top-10-Trades) wird im `finally`-Block
  geschrieben, persistiert in neuer `daily_summaries`-Tabelle, geloggt via
  `live_loop.daily_summary` und auf stdout gedruckt. Credentials via TWS
  (NFR-Sec-2): `IBKRBroker.connect()` ohne Credentials-Argumente; `Settings`
  ohne Broker-Credentials; `.env.example` dokumentiert Policy;
  `docs/SECURITY.md` (NEU) zentrale Credentials-Policy + Incident-Response.
  17 neue Tests (Journal 3, Loop 9, Summary 5). 434/434 gruen; ruff + mypy
  --strict clean. ADR-0013 akzeptiert; Tag `p5-live/5.3`.
- **Phase 7 DONE**: Slice 7.1 schliesst Phase 7 (Docker-Deployment) ab.
  Multi-Stage-`Dockerfile` (`python:3.12-slim` als builder + runtime,
  final-Image < 500 MB-Ziel) plus `.dockerignore` schliesst Caches,
  `.venv`, `data/`, `reports/`, `.git/`, `tests/`, `.env` aus. Volumes
  fuer `data/`, `reports/`, `quant_trader.sqlite` bleiben auf dem Host
  persistent. `env_file: .env` mounted Secrets zur Laufzeit, ohne sie
  ins Image zu brennen (NFR-Sec-1 erfuellt). `docker-compose.yml` mit
  Service `qtrader`, `stdin_open: true`/`tty: true` fuer interaktive
  CLI via `docker compose exec qtrader python -m quant_trader.backtest
  ...`. `scripts/entrypoint.sh` akzeptiert CLI-Args, default Streamlit.
  `.github/workflows/ci.yml` (NEU): Jobs `test` (ruff check + format
  check + mypy + pytest ohne live/slow) und `docker` (verifiziert
  `docker build .`, kein Push zu Registry). `docs/SECURITY.md`
  erweitert um Docker-Image-Sektion. 6 neue Tests
  (`tests/ops/`: Dockerfile, dockerignore, compose, CI-Workflow parsen
  + Strukturpruefungen, ohne Docker-Engine). 440/440 gruen; ruff +
  ruff-format + mypy --strict clean. ADR-0014 akzeptiert; Tag
  `p7-ops/7.1`.

## Was offen ist

| Was                                            | Wer        | Naechste Aktion                     |
|------------------------------------------------|------------|--------------------------------------|
| Phase 5 Slice 5.1 (Broker Interface + Mock + Order) | DONE    | Tag `p5-live/5.1`                   |
| Phase 5 Slice 5.2 (Live Loop + Journal + CLI)       | DONE    | Tag `p5-live/5.2`                   |
| Phase 5 Slice 5.3 (Auto-Reconnect + Summary + Credentials) | DONE | Tag `p5-live/5.3`               |
| Phase 5 als Ganzes                                | DONE    | ADR-0013 accepted                   |
| Phase 7 Slice 7.1 (Docker-Deployment + CI/CD)   | DONE      | Tag `p7-ops/7.1`                    |
| Phase 7 als Ganzes                               | DONE      | ADR-0014 accepted                   |
| Phase 6 (Risk-Adjustment / Vol-Sizing)         | spaeter    | optional nach Phase 7                |
| Phase 8+ (Cloud-Deployment, Production-Hardening) | spaeter | YAGNI fuer persoenlichen Use-Case |

## Repo-Layout zum Wiederfinden

```
docs/STATE.md                       <- diese Datei
docs/00_dev_workflow.md             <- Loop-Regeln (DE)
docs/architecture.md                <- Layered-Overview, Module-Tabelle, Datenfluss
docs/requirements/nfrs.md           <- 14 NFRs mit IDs
docs/adr/                           <- 14 Architecture Decision Records (0001-0014)
docs/prd/<phase>/<slice>.md         <- Slice-PRDs (P1+P2/2.1-P7/7.1)
docs/userstories/<phase>/...        <- US mit INVEST + Gherkin (P1-P7)
docs/uml/<phase>/<slice>.md         <- Mermaid (3 Typen, + State Machine bei Bedarf)
src/quant_trader/
  core/        types, errors, config, logging
  universe/    loader (CLI fertig)
  data/        4 Provider + FallbackDecorator + Factory + Cache + Service + CLI
strategies/    types + base + loader + SmaCross + Momentum + RSI + ETF-Rotation + Runner (alle 2.1-2.5 DONE)
backtest/      engine + portfolio + fill + sizer + metrics + report + dashboard (3.1-3.6 + Risk 4.1 DONE)
risk/          (entfaellt; Risk-Logik lebt in backtest/engine.py, ADR-0010)
live/          Broker + Realtime-Bar-Quellen + async LiveLoop + SQLite-Journal + CLI + Auto-Reconnect + Daily-Summary (5.1-5.3 DONE)
storage/       SQLite (Trade-Journal lebt in live/journal.py)
config/universe_presets.yaml
config/strategies.yaml  (sma_cross + momentum + rsi_mean_reversion, mit 2.3)
Dockerfile + docker-compose.yml + .dockerignore (NEU P7)
.github/workflows/ci.yml (CI mit test + docker jobs, NEU P7)
scripts/entrypoint.sh (NEU P7)
tests/         440 Tests, marker slow/live/integration; tests/ops/ fuer Deployment
```

## Resume-Befehl (fuer neue opencode-Session)

```
Lies:  docs/STATE.md, AGENTS.md, docs/00_dev_workflow.md, docs/architecture.md
       git log --oneline -30
       docs/adr/ (welche ADRs sind accepted/proposed?)
       docs/userstories/p3-backtest/backtest.md
       docs/uml/p3-backtest/cli.md
Frage: Slice 3.4 (CLI) Stories/UML re-approven? -> Slice-PRD erstellen
```

## Pflege

Aktualisieren bei:
- jedem Conventional Commit (Status, letzter Commit-Hash)
- Phase-Wechsel (neuer Tag)
- neuen Blockers
- Slice-Status (DRAFT -> IN_PROGRESS -> APPROVED -> DONE)

Siehe AGENTS.md Section 3 (Verification Gate) und Section 4 (Memory Model).
