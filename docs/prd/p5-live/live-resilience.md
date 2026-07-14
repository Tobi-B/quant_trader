# PRD: Slice 5.3 - Live-Loop Resilience (Auto-Reconnect + Summary + Credentials)

Phase:    P5 Live-Trading (IBKR)
Slice:    5.3 Auto-Reconnect + Tageszusammenfassung + Credentials (1 grosser Slice)
Status:   DRAFT  (User "weiter mit naechstem slice" gilt als implizite Approval; UML auf APPROVED setzen)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Den Live-Loop produktionsreif machen:
1. **Auto-Reconnect** bei TWS-Disconnect (NFR-Rel-2)
2. **Tageszusammenfassung** beim Beenden (NFR-Obs-2)
3. **Credentials-Sicherheit** via TWS-Login ohne Persistenz (NFR-Sec-2)

Damit ist Phase 5 (Live-Trading) abgeschlossen. Phase 7 (Docker-Deployment)
folgt spaeter.

## Scope (IN)

- `src/quant_trader/live/loop.py` (aendern):
  - `ReconnectConfig` (frozen dataclass): `initial_delay: float = 1.0`,
    `max_delay: float = 30.0`, `max_attempts: int = 10`
  - `LiveLoop.__init__` bekommt `reconnect_config: ReconnectConfig | None = None`
  - Neue Methode `_monitor_connection()`: alle 5s `broker.is_connected()`
    pruefen; bei `False`: `_reconnect_with_backoff()` starten
  - `_reconnect_with_backoff()`:
    - `delay = initial_delay`, `for attempt in range(1, max_attempts + 1):`
    - `await asyncio.sleep(delay)`
    - `broker.connect()` versuchen
    - bei Erfolg: subscriptions wiederherstellen, `get_positions()` re-sync
    - bei Fehler: `delay = min(delay * 2, max_delay)`
    - nach `max_attempts`: `live_loop.reconnect_failed` ERROR, raise
  - Background-Task `_monitor_connection()` wird in `run()` gestartet
    und bei Cleanup abgebrochen
  - `MockBroker` braucht KEIN reconnect (immer connected); reconnect
    wird in `if isinstance(broker, IBKRBroker)` aktiviert
- `src/quant_trader/live/types.py` (aendern): `DailySummary` (frozen
  dataclass) hinzufuegen
- `src/quant_trader/live/summary.py` (NEU, ~50 Zeilen):
  - `DailySummaryFormatter` Klasse:
    - `format(summary: DailySummary, trades: list[TradeRow]) -> str`:
      - Deutsche Tabelle mit Header, Metriken, Top-10-Trades
      - `keine Trades` bei 0 Trades
- `src/quant_trader/live/journal.py` (aendern):
  - `TradeJournal.append_summary(summary: DailySummary) -> int`:
    - Neue Tabelle `daily_summaries` (run_id, strategy_name,
      total_trades, open_positions_count, total_pnl,
      duration_seconds, closed_at)
    - `CREATE TABLE IF NOT EXISTS daily_summaries (...)`
  - `TradeJournal.list_summaries() -> list[DailySummary]`: SELECT
  - `__init__` erstellt auch `daily_summaries`-Tabelle
- `src/quant_trader/live/loop.py` (aendern):
  - Am Ende von `run()` (im `finally`-Block):
    - `summary = DailySummary(...)` mit allen Feldern
    - `journal.append_summary(summary)`
    - `log.info("live_loop.daily_summary", **asdict(summary))`
    - `print(DailySummaryFormatter.format(summary, journal.list_trades(run_id)))`
  - KeyboardInterrupt wird im `finally`-Block abgefangen, Summary
    wird trotzdem geschrieben
- `src/quant_trader/live/ibkr.py` (aendern):
  - `connect()` docstring erwaehnt: "TWS-Login erforderlich, keine
    Credentials im Code (NFR-Sec-2)"
- `src/quant_trader/core/config.py` (aendern):
  - `Settings`-Erweiterung:
    - `reconnect_initial_delay: float = 1.0`
    - `reconnect_max_delay: float = 30.0`
    - `reconnect_max_attempts: int = 10`
- `.env.example` (NEU, falls nicht vorhanden):
  - "Keine Broker-Credentials noetig. TWS-Login erfolgt manuell
    am TWS-Prompt. Siehe docs/SECURITY.md."
  - Vorhandene Settings-Keys (FMP_KEY, ALPHAVANTAGE_KEY) bleiben
- `docs/SECURITY.md` (NEU, ~30 Zeilen):
  - "API-Keys (Daten-Provider wie FMP, AlphaVantage) nur via .env"
  - "Broker-Credentials (IBKR) NUR via TWS-Login, niemals persistiert"
  - "Was tun bei Verdacht auf kompromittierte Credentials"
- Tests: `tests/live/test_loop.py`, `test_journal.py`, `test_summary.py`
  (NEU, gesamt mind. 10 neue Tests):
  - `test_reconnect_config_defaults`
  - `test_reconnect_on_disconnect_with_backoff` (mit Mock + Counter)
  - `test_reconnect_succeeds_after_n_attempts`
  - `test_reconnect_fails_after_max_attempts`
  - `test_reconnect_skipped_for_mock_broker`
  - `test_daily_summary_persisted_to_journal`
  - `test_daily_summary_log_emitted`
  - `test_daily_summary_printed_on_stdout`
  - `test_daily_summary_printed_on_keyboard_interrupt`
  - `test_daily_summary_with_zero_trades`
- Doku-Updates:
  - `docs/STATE.md`: Slice 5.3 auf DONE, Tag `p5-live/5.3`
  - `docs/adr/0013-live-resilience.md`: Status `proposed` -> `accepted`

## Out of Scope (verbindlich)

- Permanent-Failure-Handling (z.B. TWS komplett tot, OS-Restart)
- Resume von offenen Signalen nach Reconnect (Strategie setzt mit
  neuem State fort)
- Multi-Region-Redundanz
- E-Mail/Slack-Benachrichtigung bei Loop-Ende
- Web-Dashboard-Anzeige der Tageszusammenfassung
- Multi-Day-Aggregation in der Summary
- Steuer-Reports
- OAuth-Token-basierte Auth (IBKR hat keine API-Tokens)
- Credential-Rotation
- MFA-Handling (TWS-seitig)
- BacktestEngine -> LiveLoop-Bridge
- Bestehende Dateien aendern ausser den explizit genannten

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies.
- Kein `print`, kein globaler State.
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- Code englisch, CLI-/UI-Texte deutsch (NFR-Ux-1).
- **KRITISCH**: alle 417 bestehenden Tests unveraendert gruen
- Auto-Reconnect-Defaults sinnvoll (1s initial, 30s max, 10 attempts)
- Subscription-Recovery nutzt `source._subscribed` (private attr,
  aber MockBarSource hat es; IBKRBarSource tracked auch)
- `DailySummary` als frozen dataclass
- `journal.append_summary` nutzt `INSERT OR REPLACE` falls run_id
  schon existiert (Idempotenz fuer re-runs im Test)
- `SECURITY.md` auf Englisch (internationales Standard, leichter zu reviewen)

## Mapped NFRs

- NFR-Rel-2 (Live-Loop uebersteht TWS-Disconnect mit Auto-Reconnect)
- NFR-Obs-2 (Tageszusammenfassung als Log oder Report)
- NFR-Sec-2 (Broker-Credentials nur via IBKR TWS, kein persistenter Save)
- NFR-Obs-1 (structlog fuer alle reconnect/summary Events)
- NFR-Ux-1 (deutsche CLI-Texte fuer Summary)

## UML-Referenz

Visualisiert in: `docs/uml/p5-live/live-resilience.md` (Status: wird auf
APPROVED gesetzt mit diesem Slice).

## Done when

- [ ] `src/quant_trader/live/loop.py` mit Reconnect-Logik
- [ ] `src/quant_trader/live/summary.py` mit `DailySummaryFormatter`
- [ ] `src/quant_trader/live/types.py` mit `DailySummary`
- [ ] `src/quant_trader/live/journal.py` mit `append_summary` + `daily_summaries`-Tabelle
- [ ] `src/quant_trader/core/config.py` mit Reconnect-Settings
- [ ] `docs/SECURITY.md` (NEU)
- [ ] `.env.example` (NEU oder aktualisiert)
- [ ] Tests in `tests/live/` mit gesamt mind. 10 neuen Tests
- [ ] `make test` gruen (alle 417 alten + neuen Tests)
- [ ] `make lint` gruen
- [ ] `mypy --strict` gruen (0 errors)
- [ ] ADR-0013 auf "accepted"
- [ ] Conventional Commit `feat(p5-live): slice 5.3 live resilience`
- [ ] `docs/STATE.md` aktualisiert: Slice 5.3 auf DONE, Tag `p5-live/5.3`

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p5-live/live.md
cat docs/adr/0013-live-resilience.md
cat docs/uml/p5-live/live-resilience.md
cat docs/prd/p5-live/live-resilience.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht.
- **KRITISCH**: alle 417 bestehenden Tests unveraendert gruen.
- Keine bestehenden Dateien aendern ausser den genannten.

Nach dem Coden:
- Conventional Commit mit `feat(p5-live): slice 5.3 live resilience`.
- Commit-Body: warum Exponential-Backoff (Standard-Pattern, einfach
  testbar), warum `DailySummary` als separate Tabelle (historische
  Auswertung), warum keine Credentials in Settings (NFR-Sec-2).
