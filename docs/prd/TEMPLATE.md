# PRD: <Slice-Name>

Phase:    P<n> <Phase-Name>
Story:    US-P<n>.<x>  (siehe docs/userstories/p<n>/<slice>.md)
Status:   DRAFT | APPROVED | DONE
Author:   opencode
Created:  <YYYY-MM-DD>
Updated:  <YYYY-MM-DD>

## Goal

<1-2 Saetze: Was wird in diesem Slice erreicht, aus Nutzersicht?>

## Scope (IN)

- <konkretes Deliverable 1>
- <konkretes Deliverable 2>
- <konkretes Deliverable 3>

## Out of Scope (verbindlich)

- <was NICHT angefasst wird>
- <was in einer spaeteren Story / Phase kommt>
- <Scope-Creep-Schutz>

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies ausserhalb `pyproject.toml`.
- Kein `print`, kein globaler State, kein Wildcard-Import.
- Type-Hints auf allen Public-Funktionen.
- Sprache: Code englisch, Logs englisch, CLI-Strings deutsch (wo UI-relevant).

## Mapped NFRs

- NFR-<...>: <kurz>

## UML-Referenz

Visualisiert in: `docs/uml/p<n>/<slice>.md`

## Done when

- [ ] Implementierung gemaess Scope
- [ ] `make test` gruen (neue Tests decken Scope ab)
- [ ] `make lint` gruen
- [ ] `make smoke` gruen (falls anwendbar)
- [ ] Conventional Commit(s) mit Bezug auf diese PRD
- [ ] `docs/STATE.md` aktualisiert (Status Slice: DONE)
- [ ] Out-of-Scope-Items in zukuenftige PRD/Story verschoben (falls relevant)

## Anti-Drift-Reminder

Vor dem Coden:

```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p<n>/<slice>.md
cat docs/uml/p<n>/<slice>.md
cat docs/prd/p<n>/<slice>.md   # diese Datei
```

Waehrend des Codens:

- Tue **nur** das, was in `Scope (IN)` steht.
- Wenn etwas Off-Scope auftaucht: STOP, dokumentiere in Commit-Body oder STATE.md, frage Nutzer.
- Wenn Tests fehlschlagen: **erst** Tests verstehen, dann Code fixen, nicht umgekehrt.

Nach dem Coden:

- Conventional Commit mit `feat(p<n>): <slice>` oder `fix(p<n>): <...>`.
- Commit-Body enthaelt: warum diese Implementierung, was verworfen wurde.