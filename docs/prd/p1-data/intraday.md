# PRD: Slice 1.3 - Intraday Support

Phase:    P1 Datenlayer
Slice:    1.3 Intraday
Status:   APPROVED  (2026-07-08, Stories + Diagram)
Author:   opencode
Created:  2026-07-08
Updated:  2026-07-08

## Goal

Intraday-Daten (60m und 15m) optional laden, getrennt von Daily-Daten
in eigenen Cache-Pfaden ablegen, mit klarer Warnung vor hohem API-Verbrauch.

## Scope (IN)

- CLI-Flag `--granularity` akzeptiert `60m` und `15m` (in 1.2 bereits drin).
- Cache-Pfad getrennt: `data/raw/60m/<ticker>.parquet` bzw. `data/raw/15m/...`.
- Warnung `intraday.api_quota_high` beim Start eines Intraday-Fetches.
- Cache-Mechanismus (covers/read/write) funktioniert identisch fuer Intraday.
- YFinance-Mapping fuer 60m/15m Interval (in 1.2 bereits implementiert).

## Out of Scope (verbindlich)

- Realtime / Live-Streaming (Phase 5).
- Tick-Daten (Phase 5+, falls ueberhaupt).
- Andere Intraday-Intervalle als 60m und 15m.
- Intraday fuer Alpha Vantage ohne gueltigen API-Key testen (Key fehlt; yfinance deckt).

## Constraints

- AGENTS.md gilt.
- Cache-Granularitaet Pfad-Segment darf nicht mit Daily kollidieren.
- Warnung MUSS vor dem API-Call erscheinen, nicht erst danach.
- Tests muessen sowohl 60m als auch 15m abdecken.

## Mapped NFRs

- NFR-Perf-2: Intraday-Warnung wegen hoeherer API-Last.
- NFR-Data-1: Cache pro Granularitaet getrennt (kein Vermischen mit Daily).

## UML-Referenz

Visualisiert in: `docs/uml/p1-data/intraday.md`

## Done when

- [ ] Warnung `intraday.api_quota_high` wird vor Intraday-Fetches geloggt.
- [ ] Cache-Pfade `data/raw/60m/...` und `data/raw/15m/...` separat.
- [ ] Tests: Cache-Granularitaets-Trennung, DataService-Warnung bei Intraday.
- [ ] Smoke-Test mit 60m und yfinance (z.B. SPY letzte 5 Tage) liefert Parquet-Datei.
- [ ] `make lint`, `make test` gruen.
- [ ] Tag `p1-intraday` gesetzt.