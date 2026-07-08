# Non-Functional Requirements (NFRs)

Cross-cutting Constraints. Werden pro Phase/Slice von UML-Diagrammen und/oder
Slice-PRDs referenziert. Jede NFR hat eine stabile ID.

ID-Format: `NFR-<Kategorie>-<Nr>`. Kategorien:

| Kategorie   | Zweck                                              |
|-------------|----------------------------------------------------|
| `Sec`       | Security (Secrets, Auth, Netzwerk, Daten)         |
| `Rel`       | Reliability (Reconnect, Backups, Idempotenz)       |
| `Perf`      | Performance (Latenz, Throughput, Limits)           |
| `Obs`       | Observability (Logs, Metriken, Alerts)             |
| `Ux`        | User Experience / CLI-Ergonomie                    |
| `Data`      | Datenintegritaet (Cache, Korpus, Korrektheit)      |
| `Ops`       | Operations / Deployment (Docker, Scheduler)       |

## NFR-Liste

| ID            | Statement (kurz)                                              | Phase | Status   |
|---------------|---------------------------------------------------------------|-------|----------|
| NFR-Sec-1     | API-Keys nur via `.env`, niemals im Repo committen           | P1    | APPROVED |
| NFR-Sec-2     | Broker-Credentials nur via IBKR TWS, kein persistenter Save   | P5    | DRAFT    |
| NFR-Rel-1     | Daten-Fetch idempotent: wiederholte Aufrufe liefern gleiche Daten | P1 | APPROVED |
| NFR-Rel-2     | Live-Loop uebersteht TWS-Disconnect mit Auto-Reconnect       | P5    | DRAFT    |
| NFR-Rel-3     | Order-Manager idempotent: gleiche ClientOrderId nicht zweimal senden | P5 | DRAFT |
| NFR-Perf-1    | Backtest ueber 5 Jahre Taeglich-Daten < 30 s                  | P3    | DRAFT    |
| NFR-Perf-2    | Daten-Fetch fuer ein Ticker 5 Jahre < 60 s (Cache-Miss)      | P1    | APPROVED |
| NFR-Obs-1     | Strukturiertes Logging (structlog JSON in Produktion)         | P0    | APPROVED |
| NFR-Obs-2     | Tageszusammenfassung (P&L, offene Positionen) als Log oder Report | P5 | DRAFT    |
| NFR-Ux-1      | CLI-Texte auf Deutsch, Fehlermeldungen klar und actionable    | P0    | APPROVED |
| NFR-Data-1    | Parquet-Cache mit Inkrement-Update (kein Full-Refetch bei Overlap) | P1 | APPROVED |
| NFR-Data-2    | Adj. Close verwendet fuer Rueckrechnungen (Corporate Actions) | P1  | APPROVED |
| NFR-Ops-1     | Lokale Entwicklung + spaeteres Docker-Deployment             | P7    | DRAFT    |

## Neue NFRs anlegen

1. Neue Zeile in der Tabelle einfuegen, Status `DRAFT`.
2. Begruendung in einer ADR (`docs/adr/NNNN-<slug>.md`), wenn Architektur-relevant.
3. Mindestens ein UML-Diagramm in `docs/uml/` referenziert die ID.
4. Erst dann auf `APPROVED` setzen, wenn Slice mit der NFR committet ist.

## Verweise

- Diagramme: `docs/uml/<phase>/<slice>.md` (Header `Mapped Requirements`).
- Stories: `docs/userstories/<phase>/<slice>.md` (Acceptance-Criteria koennen NFRs referenzieren).
- ADRs: `docs/adr/NNNN-<title>.md`.