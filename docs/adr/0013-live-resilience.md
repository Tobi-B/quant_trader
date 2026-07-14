# ADR 0013: Live-Loop Robustness (Auto-Reconnect + Daily-Summary + Credentials)

Status:     accepted
Datum:      2026-07-14
Phase:      P5 Live-Trading
Supersedes: -
Superseded by: -

## Context

Slice 5.2 hat den Live-Loop mit Trade-Journal und Live-CLI geliefert.
Fueer produktives Live-Trading fehlen noch drei Robustheits-Features:

1. **Auto-Reconnect** (NFR-Rel-2): TWS-Disconnects sind in der Praxis
   haeufig (Network-Blips, TWS-Restart, TWS-Update). Der Loop muss
   resilient sein.
2. **Tageszusammenfassung** (NFR-Obs-2): Nach Loop-Ende soll der
   Trader sofort sehen, wie der Tag gelaufen ist (Trades, P&L,
   offene Positionen).
3. **Credentials-Sicherheit** (NFR-Sec-2): IBKR-Credentials duerfen
   niemals persistiert werden. TWS-Login erfolgt manuell am TWS-Prompt.

Diese drei Features sind eng miteinander verknuepft (alle drei
betreffen den LiveLoop-Lifecycle) und werden daher in **einem Slice
(5.3)** umgesetzt.

## Decision

### 1. Auto-Reconnect (US-P5.3)

**Architektur**:
- `LiveLoop` bekommt `_reconnect_config: ReconnectConfig` (frozen
  dataclass: `initial_delay: float = 1.0`, `max_delay: float = 30.0`,
  `max_attempts: int = 10`)
- `IBKRBroker.is_connected()` wird zyklisch alle 5s geprueft
  (Background-Task)
- Bei Disconnect: `live_loop.broker_disconnected` WARNING,
  `_reconnect_with_backoff()` starten
- `_reconnect_with_backoff()`:
  - `delay = initial_delay`
  - fuer i in 1..max_attempts:
    - `await asyncio.sleep(delay)`
    - `broker.connect()` versuchen
    - bei Erfolg: `live_loop.reconnected` INFO, subscriptions wieder-
      herstellen, `broker.get_positions()` re-sync, return
    - bei Fehler: `delay = min(delay * 2, max_delay)`,
      `live_loop.reconnect_attempt_failed` WARNING
  - nach `max_attempts` erfolglos: `live_loop.reconnect_failed`
    ERROR, Loop beendet mit Exit 1
- Subscription-Recovery: `source.subscribe(ticker)` fuer jeden
  initial subscribed ticker (via `source._subscribed: set[str]`)
- **MockBroker**: `is_connected()` returnt immer True, kein Reconnect

### 2. Tageszusammenfassung (US-P5.4)

**Architektur**:
- Neue Komponente `DailySummary` (frozen dataclass):
  - `run_id: str`, `strategy_name: str`, `total_trades: int`,
    `open_positions_count: int`, `total_pnl: float`,
    `duration_seconds: float`, `closed_at: str`
- `TradeJournal.append_summary(summary: DailySummary) -> int`:
  - Neue Tabelle `daily_summaries` (run_id, strategy_name,
    total_trades, open_positions_count, total_pnl, duration_seconds,
    closed_at)
- `DailySummaryFormatter.format(summary: DailySummary,
  trades: list[TradeRow]) -> str`:
  - Deutsche Tabelle mit Header + Metriken + Top-10-Trades
- `LiveLoop.run` schreibt am Ende: `summary = DailySummary(...)`,
  `journal.append_summary(summary)`,
  `log.info("live_loop.daily_summary", **asdict(summary))`,
  `print(DailySummaryFormatter.format(summary, journal.list_trades(run_id)))`
- Wird auch bei KeyboardInterrupt aufgerufen (in `finally`-Block)

### 3. Credentials-Sicherheit (US-P5.5)

**Architektur**:
- `IBKRBroker.connect(host, port, client_id)` ruft `ib.connect(host,
  port, clientId)` OHNE Credentials-Argumente. TWS-Login erfolgt
  manuell am TWS-Prompt (IBKR-Sicherheitsmodell).
- `Settings` hat KEINE `username`, `password`, `api_key`-Felder.
  Bestehende Felder `ibkr_host`, `ibkr_port`, `ibkr_client_id` sind
  nicht-credentials.
- `.env.example` (oder `.env.template` falls nicht vorhanden):
  - Wird erstellt mit Kommentar: "Keine Broker-Credentials noetig.
    TWS-Login erfolgt manuell am TWS-Prompt."
- `docs/SECURITY.md` (NEU, ~30 Zeilen): dokumentiert die
  Credentials-Policy:
  - "API-Keys nur via .env (NFR-Sec-1) fuer Daten-Provider (FMP, AV, etc.)"
  - "Broker-Credentials (IBKR) NUR via TWS-Login, niemals persistiert
    (NFR-Sec-2)"
  - "Was zu tun ist bei Verdacht auf kompromittierte Credentials"
- `IBKRBroker` Quellcode-Kommentar (docstring) erwaehnt explizit
  "TWS-Login erforderlich, keine Credentials im Code"

### 4. Settings-Erweiterung

```python
class Settings(BaseSettings):
    # ... existing
    reconnect_initial_delay: float = 1.0
    reconnect_max_delay: float = 30.0
    reconnect_max_attempts: int = 10
```

### 5. Backward-Compat

- Alle 417 bestehenden Tests unveraendert gruen
- Defaults fuer neue Reconnect-Config = 1.0s / 30.0s / 10 (sinnvolle Werte)
- `IBKRBroker.connect` aendert Signatur NICHT (existierende Tests
  bleiben valid)

## Consequences

**Positiv**
- Live-Trading ist produktionsreif: Auto-Reconnect, Tagesabschluss,
  Credentials-Sicherheit
- Tageszusammenfassung in DB ermoeglicht historische Auswertung
- SECURITY.md dokumentiert Credentials-Policy zentral
- Auto-Reconnect mit Exponential-Backoff ist Standard-Pattern
- Bei MockBroker (Tests): kein Overhead, alle 417 Tests gruen

**Negativ**
- `IBKRBroker` wird in 5.3 noch komplexer (Subscription-Tracking)
- Subscription-Recovery setzt voraus, dass `MockBarSource._subscribed`
  getrackt wird; falls das nicht der Fall ist, muss es nachgeruestet
  werden
- Tageszusammenfassung im Journal benoetigt Schema-Migration bei
  bestehenden DBs (Pragmatisch: `CREATE TABLE IF NOT EXISTS` reicht
  fuer neue DBs; bestehende DBs aus 5.2-Tests in tmp_path sind OK)

**Neutral**
- `SECURITY.md` ist neu; das Projekt hatte vorher keine dedizierte
  Security-Doku
- `DailySummaryFormatter` Pattern aehnlich zu `ConsoleFormatter` aus
  Phase 3 (Konsistenz)

## Alternatives Considered

- **TWS-Auth via ib_insync API-Key**: abgelehnt, IBKR hat keinen
  API-Key-Modus (nur TWS-Login)
- **Auto-Reconnect mit WebSocket-Retry-Library** (z.B. tenacity):
  abgelehnt, eigener simpler Backoff reicht und ist testbar
- **Tageszusammenfassung als PDF/HTML-Report**: abgelehnt, ASCII-
  Tabelle auf stdout + DB-Eintrag reicht fuer P5
- **Credentials in macOS-Keychain speichern**: abgelehnt, NFR-Sec-2
  sagt explizit "kein persistenter Save"
- **Tageszusammenfassung in separater DB-Tabelle oder separate Datei**:
  abgelehnt, gleiche SQLite-DB wie `trades` reicht
- **3 separate Slices (5.3, 5.4, 5.5)**: User-Praeferenz war "1 grosser
  Slice" fuer schnelleren Durchsatz (analog Slice 4.1)

## References

- `src/quant_trader/live/` (erweitert in 5.3)
- `src/quant_trader/core/config.py` (Settings-Erweiterung)
- `docs/userstories/p5-live/live.md` (US-P5.3, US-P5.4, US-P5.5)
- `docs/prd/p5-live/live-resilience.md` (Slice-PRD)
- `docs/uml/p5-live/live-resilience.md` (Mermaid Structure/Flow/Sequence)
- `docs/SECURITY.md` (NEU)
- NFR-Rel-2 (Auto-Reconnect)
- NFR-Obs-2 (Tageszusammenfassung)
- NFR-Sec-2 (Credentials via TWS only)
- ADR-0011 (Broker-Interface-Architektur, Pattern)
- ADR-0012 (Live-Loop-Architektur, Pattern)
