# UML-Diagramme

Pro Phase ein oder mehrere Slices. Jeder Slice bekommt **drei** Mermaid-Diagramme:

| Diagramm     | Zweck                                                    |
|--------------|----------------------------------------------------------|
| Structure    | Module, Klassen, Interfaces, Abhaengigkeiten             |
| Flow         | Laufzeit-Kontrollfluss (Activity/Flowchart)              |
| Sequence     | Nachrichten-/Methodenaufrufe ueber Zeit                  |

## Konvention

- Pfad: `docs/uml/<phase>/<slice>.md` (z.B. `docs/uml/p1-data/cache.md`).
- Header:
  ```
  Status:    DRAFT | APPROVED
  Phase:     P1 Datenlayer
  Slice:     Cache
  Approved:  <datum>
  ```
- Inhaltsprache: Englisch (Mermaid-Labels), Dokumentations-Text: Deutsch.
- Status-Uebergaenge nur durch Nutzer-Freigabe (APPROVED).

## Workflow

1. Agent draftet die Diagramme (Status: DRAFT).
2. Nutzer reviewt.
3. APPROVED oder Aenderungen.
4. Erst dann Code.

## Pruefung

```bash
make uml-check
```

Nutzt `mmdc` (mermaid-cli), falls installiert. Ohne mmdc: manuell im GitHub-PR-Review.