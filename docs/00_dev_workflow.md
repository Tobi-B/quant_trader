# Entwicklungs-Workflow

Dieses Dokument beschreibt den praktischen Loop, dem opencode (und andere Agenten) folgen.

## Phasen-Loop

Jede Phase (`P0` bis `P8`) folgt diesem Ablauf:

```
1. Interview
   Ich (opencode) draft 3-6 User Stories nach INVEST + Gherkin + MoSCoW + T-Shirt-Size.
   Du: APPROVED | aendere | neue Stories.

2. UML-Diagramme
   Drei Mermaid-Diagramme pro Slice:
     - docs/uml/<phase>/<slice>.md  -> Structure
     - docs/uml/<phase>/<slice>.md  -> Flow
     - docs/uml/<phase>/<slice>.md  -> Sequence
   Status: DRAFT, dann APPROVED nach Review.

3. Implementierung
   Erst nach APPROVED. Tests, Lint, Smoke.

4. Commit
   Conventional Commits, ein logischer Schritt pro Commit.
   Phase-Tag (p0, p1, ...).
```

## Standard-Befehle

| Befehl         | Zweck                                         |
|----------------|-----------------------------------------------|
| `make install` | `uv sync --all-extras`                        |
| `make lint`    | ruff check + ruff format --check              |
| `make format`  | auto-fix (Linting + Formatierung)             |
| `make test`    | pytest ohne `live` und `slow`                 |
| `make smoke`   | minimaler End-to-End-Backtest                 |
| `make data`    | Daten-Fetch-Skript (Argumente: `TICKER=...`)  |
| `make clean`   | Caches loeschen                               |

## Wann ist eine Phase "done"?

- Alle Stories haben gruene Gherkin-Akzeptanztests.
- `make lint`, `make test`, `make smoke` sind gruen.
- Phase-Tag ist gesetzt.
- Diagramm-Datei in `docs/uml/` hat Status: APPROVED.

## Memory bei Session-Start

```
git log --oneline -30
git status
docs/00_dev_workflow.md lesen
```

Nicht den gesamten Code neu lesen - `git log` ist das Gedaechtnis.