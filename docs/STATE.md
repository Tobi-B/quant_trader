# QuantTrader - Session Resume

> **Anker fuer Session-Resume.** Diese Datei macht den aktuellen Projektzustand
> in einem einzigen Blick lesbar. Vor jedem Coden: diese Datei lesen + dann PRD/User-Story/UML.

## Schnappschuss

| Feld                  | Wert                                                |
|-----------------------|------------------------------------------------------|
| Datum                 | 2026-07-10                                          |
| Letzter Commit (main) | `bf1f9a9`                                           |
| Branch                | `main` (clean, alle Aenderungen gepusht)              |
| Tests                 | 153/153 gruen                                       |
| Lint + Format         | gruen                                               |
| Aktive Phase          | P2 Strategien                                       |
| Aktiver Slice         | 2.4 ETF-Rotation - IN_PROGRESS                      |
| Open Decision         | -                                                    |

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
| `p2-strategies/2.4` | ETF-Rotation        | 2026-07-10 | IN_PROGRESS |
| `p2-strategies/2.5` | Signal-Runner CLI   | offen  | DRAFT      |

## Was steht (verifiziert)

- **CLI** `python -m quant_trader.universe {load,list}` und
  `python -m quant_trader.data TICKER [--universe ...] [--granularity daily|60m|15m]`
- **Provider-Chain**: AlphaVantage (Premium-only) -> YFinance -> StockData.org
- **Cache**: Parquet unter `data/raw/{daily,60m,15m}/<TICKER>.parquet`, idempotent
- **Universe YAML**: `config/universe_presets.yaml` (sp500/dax40/etfs)
- **.env (gitignored)**: AV-Key hinterlegt (Premium-Endpoint, daher Fallback-Kette aktiv)
- **CLI-Smoke** 6 Schritte demonstriert in `Sprint-Demo` oben.
- **P2 Doku APPROVED** (22e6300): US-P2.1+US-P2.2 freigegeben, framework.md
  + runner.md UMLs APPROVED, Slice 2.1 PRD erstellt.
- **Architecture-Doku** (53ab219): `docs/architecture.md` mit Layered-Overview,
  Module-Tabelle, Datenfluss. `docs/adr/` mit 8 ADRs (0001-0008).
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

## Was offen ist

| Was                                            | Wer        | Naechste Aktion                     |
|------------------------------------------------|------------|--------------------------------------|
| Slice 2.4 Slice-PRD + Implementation            | opencode   | EtfRotationStrategy                  |
| Slice 2.5                                       | spaeter    | Signal-Runner-CLI                    |
| Phase 3 (Backtest-Engine + Reports)            | spaeter    | Nach Phase 2                          |
| Phase 5 (Live Trading IBKR, Paper first)       | spaeter    | Nach Phase 3                          |
| Phase 7 (Docker-Deployment)                    | spaeter    | Nach Phase 5                          |
| Pre-existing mypy-Errors in core/logging.py    | Optional   | 2 Lines Fix, nicht im Slice-Scope    |

## Repo-Layout zum Wiederfinden

```
docs/STATE.md                       <- diese Datei
docs/00_dev_workflow.md             <- Loop-Regeln (DE)
docs/architecture.md                <- Layered-Overview, Module-Tabelle, Datenfluss
docs/requirements/nfrs.md           <- 13 NFRs mit IDs
docs/adr/                           <- 8 Architecture Decision Records (0001-0008)
docs/prd/<phase>/<slice>.md         <- Slice-PRDs (P1+P2/2.1 ausgearbeitet)
docs/userstories/<phase>/...        <- US mit INVEST + Gherkin (P1+P2)
docs/uml/<phase>/<slice>.md         <- Mermaid (3 Typen, + State Machine bei Bedarf)
src/quant_trader/
  core/        types, errors, config, logging
  universe/    loader (CLI fertig)
  data/        3 Provider + FallbackDecorator + Factory + Cache + Service + CLI
strategies/    types + base + loader + SmaCross + Momentum + RSI (2.1+2.2+2.3 DONE); ETF-Rotation, Runner folgen
backtest/      (P3 kommt)
risk/          (P4 kommt)
live/          (P5 kommt)
storage/       SQLite (P5 kommt)
config/universe_presets.yaml
config/strategies.yaml  (sma_cross + momentum + rsi_mean_reversion, mit 2.3)
tests/         153 Tests, marker slow/live/integration
```

## Resume-Befehl (fuer neue opencode-Session)

```
Lies:  docs/STATE.md, AGENTS.md, docs/00_dev_workflow.md, docs/architecture.md
       git log --oneline -30
       docs/adr/ (welche ADRs sind accepted/proposed?)
       docs/userstories/p2-strategies/strategies.md
       docs/uml/p2-strategies/rotation.md
Frage: Slice 2.4 Stories/UML re-approven? -> Slice-PRD erstellen
```

## Pflege

Aktualisieren bei:
- jedem Conventional Commit (Status, letzter Commit-Hash)
- Phase-Wechsel (neuer Tag)
- neuen Blockers
- Slice-Status (DRAFT -> IN_PROGRESS -> APPROVED -> DONE)

Siehe AGENTS.md Section 3 (Verification Gate) und Section 4 (Memory Model).
