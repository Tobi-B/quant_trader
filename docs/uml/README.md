# UML-Diagramme

Pro Phase ein oder mehrere Slices. Jeder Slice bekommt **drei** Mermaid-Diagramme:

| Diagramm     | Zweck                                                    |
|--------------|----------------------------------------------------------|
| Structure    | Module, Klassen, Interfaces, Abhaengigkeiten             |
| Flow         | Laufzeit-Kontrollfluss (Activity/Flowchart)              |
| Sequence     | Nachrichten-/Methodenaufrufe ueber Zeit                  |

State Machine ist optional und kommt nur fuer Slices mit stateful entities (z.B. Phase 5 Order-Lifecycle).

## Requirements-Kopplung

Jedes Diagramm visualisiert mindestens ein Requirement (NFR oder Slice-spezifisch). Mapping:

| Requirement-Typ            | UML-Diagramm                |
|----------------------------|------------------------------|
| Strukturell                | Structure                    |
| Verhalten / Ablauf         | Flow                         |
| Interaktion                | Sequence                     |
| Lifecycle / Zustand        | State Machine (optional)     |

NFRs leben in `docs/requirements/nfrs.md` (ID-Format `NFR-<Kategorie>-<Nr>`, z.B. `NFR-Sec-1`).

## Konvention

- Pfad: `docs/uml/<phase>/<slice>.md` (z.B. `docs/uml/p1-data/cache.md`).
- Header:
  ```
  Status:    DRAFT | APPROVED
  Phase:     P1 Datenlayer
  Slice:     Cache
  Approved:  <datum>

  Mapped Requirements:
  - NFR-Sec-1: ...
  - NFR-Perf-2: ...
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