# QuantTrader - Session Resume

> **Anker fuer Session-Resume.** Diese Datei macht den aktuellen Projektzustand
> in einem einzigen Blick lesbar. Vor jedem Coden: diese Datei lesen + dann PRD/User-Story/UML.

## Schnappschuss

| Feld                  | Wert                                                |
|-----------------------|------------------------------------------------------|
| Datum                 | 2026-07-08                                          |
| Letzter Commit (main) | `bd66529`                                           |
| Branch                | `main` (clean, alle Aenderungen gepusht)              |
| Tests                 | 84/84 gruen                                         |
| Lint + Format         | gruen                                               |
| Aktive Phase          | P2 Strategien                                       |
| Open Decision         | Phase-2-UML wartet auf User-APPROVED                  |

## Phasen-Tags (chronologisch)

| Tag            | Phase                  | Datum       | Status    |
|----------------|------------------------|-------------|-----------|
| `p0`           | Harness + Bootstrap    | 2026-07-08  | abgeschlossen |
| `p1-universe`  | Universe Loader        | 2026-07-08  | abgeschlossen |
| `p1-data`      | DataProvider + Cache   | 2026-07-08  | abgeschlossen |
| `p1-intraday`  | Intraday Support       | 2026-07-08  | abgeschlossen |
| `p2-strategies`| Strategien             | offen       | UML pending |

## Was steht (verifiziert)

- **CLI** `python -m quant_trader.universe {load,list}` und
  `python -m quant_trader.data TICKER [--universe ...] [--granularity daily|60m|15m]`
- **Provider-Chain**: AlphaVantage (Premium-only) -> YFinance -> StockData.org
- **Cache**: Parquet unter `data/raw/{daily,60m,15m}/<TICKER>.parquet`, idempotent
- **Universe YAML**: `config/universe_presets.yaml` (sp500/dax40/etfs)
- **.env (gitignored)**: AV-Key hinterlegt (Premium-Endpoint, daher Fallback-Kette aktiv)
- **CLI-Smoke** 6 Schritte demonstriert in `Sprint-Demo` oben.

## Was offen ist

| Was                                            | Wer        | Naechste Aktion                     |
|------------------------------------------------|------------|--------------------------------------|
| Phase-2-UML-Diagramme APPROVED                  | Nutzer     | `APPROVED` oder Aenderungen sagen   |
| Slice 2.1-2.5 Implementation                   | nach OK    | User-Stories APPROVED + Diagramme   |
| Phase 3 (Backtest-Engine + Reports)            | spaeter    | Nach Phase 2                          |
| Phase 5 (Live Trading IBKR, Paper first)       | spaeter    | Nach Phase 3                          |
| Phase 7 (Docker-Deployment)                    | spaeter    | Nach Phase 5                          |

## Repo-Layout zum Wiederfinden

```
docs/STATE.md                       <- diese Datei
docs/00_dev_workflow.md             <- Loop-Regeln (DE)
docs/requirements/nfrs.md           <- 13 NFRs mit IDs
docs/prd/<phase>/<slice>.md         <- Slice-PRDs (P1 ausgearbeitet)
docs/userstories/<phase>/...        <- US mit INVEST + Gherkin (P1+P2)
docs/uml/<phase>/<slice>.md         <- Mermaid (3 Typen, + State Machine bei Bedarf)
src/quant_trader/
  core/        types, errors, config, logging
  universe/    loader (CLI fertig)
  data/        3 Provider + FallbackDecorator + Factory + Cache + Service + CLI
strategies/    (P2 kommt)
backtest/      (P3 kommt)
risk/          (P4 kommt)
live/          (P5 kommt)
storage/       SQLite (P5 kommt)
config/universe_presets.yaml
tests/         84 Tests, marker slow/live/integration
docs/architecture.md  (nicht erstellt - Mini-Hinweis: bei Bedarf)
```

## Resume-Befehl (fuer neue opencode-Session)

```
Lies:  docs/STATE.md, AGENTS.md, docs/00_dev_workflow.md
       git log --oneline -30
       docs/uml/p2-strategies/*.md
       docs/userstories/p2-strategies/strategies.md
Frage: P2 UML approved? -> weiter mit Slice 2.1
```

## Pflege

Aktualisieren bei:
- jedem Conventional Commit (Status, letzter Commit-Hash)
- Phase-Wechsel (neuer Tag)
- neuen Blockers
- Slice-Status (DRAFT -> IN_PROGRESS -> APPROVED -> DONE)

Siehe AGENTS.md Section 3 (Verification Gate) und Section 4 (Memory Model).
