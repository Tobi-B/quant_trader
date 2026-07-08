# Slice-PRD-Pattern

PRD (Product Requirements Document) pro Slice, **eine Datei pro Arbeitseinheit**. Verbindlich fuer jeden Slice, der autonom oder im Loop abgearbeitet wird.

## Zweck

- **Anti-Context-Rot**: Disk-State statt Chat-Verlauf. Eine PRD-Datei ist die Single Source of Truth fuer einen Slice.
- **Scope-Creep-Schutz**: explizite Out-of-Scope-Sektion.
- **Reproduzierbarkeit**: Neue Session / Loop-Iteration sieht PRD + STATE + git log und weiss, was zu tun ist.
- **Done-when-Klarheit**: harte Abbruchkriterien, automatisierbar (Tests, Lint, Smoke).

## Wann nutzen?

- Bei jedem Slice, der autonom abgearbeitet werden soll (auch im Loop).
- Bei nicht-trivialen Slices (> 1 Datei, mehrere Stunden Aufwand).
- Bei Slices mit Sicherheits-/Architektur-Relevanz (Phase 5+).

Fuer einfache Slices (1-2 Dateien, < 1 h) reicht die User-Story-Datei.

## Konvention

- Pfad: `docs/prd/<phase>/<slice>.md` (z.B. `docs/prd/p1-data/parquet-cache.md`).
- Sprache: Deutsch fuer Erklaerungen, Englisch fuer technische Begriffe.
- Status: `DRAFT | APPROVED | DONE`.

## Workflow

1. PRD wird **nach** APPROVED-User-Story erstellt.
2. PRD referenziert User-Story-ID und NFR-IDs.
3. PRD wird vom Nutzer APPROVED (Soft-Gate).
4. Implementierung folgt PRD wörtlich. Abweichungen werden in `STATE.md` oder Commit-Body dokumentiert.
5. Nach `make test/lint/smoke` gruen: Status auf `DONE`, Conventional Commit, `STATE.md` aktualisieren.

## Pruefung

PRD ist vollstaendig, wenn:

- Goal in 1-2 Saetzen
- Scope klar abgegrenzt
- Out-of-Space explizit
- Done-when-Checkliste vollstaendig
- NFR-Referenzen vorhanden (sofern einschlaegig)

Siehe `docs/prd/TEMPLATE.md`.