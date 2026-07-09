# Phase 2 - Strategien: User Stories

Phase:    P2 Strategien
Status:   APPROVED  (2026-07-10, US-P2.1 + US-P2.2 fuer Slice 2.1,
                    US-P2.3 + US-P2.4 fuer Slice 2.2 freigegeben)
Persona:  Tobias (privater Einsteiger-Trader)
Quelle:   Interview am 2026-07-08

Konvention: jede Story folgt INVEST + MoSCoW + T-Shirt-Size + Gherkin.
Nutzer-zentriert: das "Was & Warum", nicht das "Wie".

Hinweis: Backtest-Engine und Metriken sind Phase 3. Hier in Phase 2
generieren Strategien nur Signale, die spaeter von der Engine ausgefuehrt
werden. Strategien sind aber bereits isoliert testbar (Smoke-CLI in Slice 2.5).

---

## Slice 2.1 - Strategy Framework

### US-P2.1 - Einheitliche Strategy-Schnittstelle

- **Als** Trader
- **moechte ich**, dass alle Strategien die gleiche Schnittstelle haben,
- **damit** ich sie austauschen kann, ohne den Backtest-Code zu aendern.

- **Priority:** Must
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** ich habe eine Strategie-Klasse
  - **When** ich `strategy.on_bar(bar, portfolio) -> list[Signal]` aufrufe
  - **Then** erhalte ich 0-N Signale (BUY, SELL oder HOLD)
  - **And** Signale enthalten mindestens: Ticker, Aktion (BUY/SELL), Konfidenz optional
  - **And** Strategien haben einen Namen und versionierte Parameter

- **Out of Scope:** Backtest-Ausfuehrung (Phase 3); Live-Trading (Phase 5).

### US-P2.2 - Strategie-Parameter aus YAML

- **Als** Trader
- **moechte ich** Strategie-Parameter in einer YAML-Datei pflegen,
- **damit** ich Strategien tunen kann, ohne Python-Code zu aendern.

- **Priority:** Must
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** `config/strategies.yaml` mit Parametern je Strategie
  - **When** ich `StrategyBase.from_config("sma_cross", config)` aufrufe
  - **Then** wird die richtige Strategie-Klasse instanziiert mit den richtigen Werten
  - **And** fehlende Datei oder Section erzeugt einen klaren Fehler
  - **And** unbekannte Strategie-Namen erzeugen einen klaren Fehler mit Liste der verfuegbaren

- **Out of Scope:** Live-Reload waehrend Backtest; UI fuer Parameter.

---

## Slice 2.2 - Trendfolger (SMA-Cross + Momentum)

### US-P2.3 - SMA-Crossover Strategie

- **Als** Trader
- **moechte ich** eine SMA-Cross-Strategie nutzen,
- **damit** ich Trendfolger auf Basis gleitender Durchschnitte backtesten kann.

- **Priority:** Must
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** SMA-Perioden (z.B. 20 und 50) als Parameter
  - **When** der schnelle SMA den langsamen SMA von unten nach oben kreuzt
  - **Then** wird ein BUY-Signal fuer den Ticker generiert
  - **And** bei Kreuzung von oben nach unten ein SELL-Signal
  - **And** in der ersten N Bars (warmup) keine Signale (nicht genug Historie)
  - **And** bei unzureichender Historie (z.B. < langsamster Periode) kein Signal

- **Out of Scope:** mehrere Ticker parallel; Signalstaerke (Confidence).

### US-P2.4 - Momentum 12-1 Strategie

- **Als** Trader
- **moechte ich** eine Momentum-Strategie (12 Monate Return, ohne den letzten Monat) nutzen,
- **damit** ich klassische Jahres-Performance nutzen kann.

- **Priority:** Must
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** Lookback-Perioden (z.B. 12-1 Monate) und ein Universum von Tickern
  - **When** am Ende jedes Monats die Performance berechnet wird
  - **Then** wird ein BUY-Signal fuer die Top-N Performer generiert
  - **And** ein SELL-Signal fuer Positionen, die nicht mehr in den Top-N sind
  - **And** in der ersten 12 Monate keine Signale (kein voller Lookback)
  - **And** Rebalancing-Frequenz (default: monatlich) ist konfigurierbar

- **Out of Scope:** Volatility-adjustierte Position-Groessen; Bond-Alternative fuer 0-Momentum-Perioden.

---

## Slice 2.3 - Mean-Reversion

### US-P2.5 - RSI Mean-Reversion Strategie

- **Als** Trader
- **moechte ich** eine RSI-Strategie nutzen,
- **damit** ich ueberverkaufte Werte kaufen und ueberkaufte verkaufen kann.

- **Priority:** Must
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** RSI-Periode (default 14) und Schwellen (default 30/70)
  - **When** RSI unter die untere Schwelle faellt
  - **Then** wird ein BUY-Signal generiert
  - **And** wenn RSI ueber die obere Schwelle steigt: SELL-Signal
  - **And** in der ersten RSI-Periode Bars kein Signal (kein voller RSI)
  - **And** Signale nur bei Crossings (nicht statisch halten)

- **Out of Scope:** Multi-Timeframe; Divergenz-Erkennung.

---

## Slice 2.4 - ETF-Rotation

### US-P2.6 - ETF Top-N Momentum Rotation

- **Als** Trader
- **moechte ich** monatlich in die Top-N ETFs nach 6-Monats-Momentum rotieren,
- **damit** ich nur in staerkste Asset-Klassen investiert bin.

- **Priority:** Must
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** ETF-Universum und Top-N (default 2)
  - **When** am Monatsende die 6-Monats-Performance pro ETF berechnet wird
  - **Then** werden die Top-N ETFs gewaehlt und gleichgewichtet
  - **And** ein SELL-Signal fuer ETFs ausserhalb der Top-N
  - **And** in den ersten 6 Monaten keine Signale (kein voller Lookback)
  - **And** Cash-Anteil wenn keiner der ETFs positive 6-Monats-Performance hat
  - **And** Position-Gewichtung gleich (z.B. 1/N pro ETF)

- **Out of Scope:** Volatility-Adjustment; Bond-Hedge; Bond+Equity 60/40 Mischformen.

---

## Slice 2.5 - Signal-Runner (Smoke-CLI)

### US-P2.7 - Strategie-Signale ohne Backtest ausgeben

- **Als** Trader
- **moechte ich** Signale einer Strategie auf historische Daten generieren und ausgeben,
- **damit** ich die Strategie schnell pruefen kann, ohne den vollen Backtest.

- **Priority:** Should
- **Estimate:** S
- **Acceptance Criteria (Gherkin):**
  - **Given** eine Strategie und historische Bars fuer einen Ticker
  - **When** ich `python -m quant_trader.strategies run --strategy sma_cross --ticker SPY --start 2024-01-02 --end 2024-06-30` aufrufe
  - **Then** werden alle Signale (Datum, Ticker, Aktion) als Tabelle/JSON ausgegeben
  - **And** die Strategie nutzt den Cache aus Phase 1
  - **And** die Ausgabe ist auf 100 Zeilen begrenzt (zu viele sonst)
  - **And** unbekannte Strategie erzeugt klaren Fehler mit Liste

- **Out of Scope:** Signal-Backtest mit P&L (Phase 3); Equity-Curve (Phase 3).

---

## Mapped NFRs (siehe docs/requirements/nfrs.md)

| Story  | NFR-IDs                                       |
|--------|------------------------------------------------|
| US-P2.1 | NFR-Ux-1 (klare API)                           |
| US-P2.2 | NFR-Ux-1, NFR-Sec-1 (keine Secrets in YAML)     |
| US-P2.3 | NFR-Perf-2 (schnelle Berechnung)                |
| US-P2.4 | NFR-Perf-2                                      |
| US-P2.5 | NFR-Perf-2                                      |
| US-P2.6 | NFR-Perf-2                                      |
| US-P2.7 | NFR-Obs-1 (Logs), NFR-Data-1 (Cache-Nutzung)    |

---

## Definition of Done (alle Stories)

- [ ] StrategyBase + alle 4 Strategien implementiert
- [ ] YAML-Loader funktioniert
- [ ] Signal-Runner CLI funktioniert mit echtem Cache
- [ ] Tests: StrategyBase-Interface, jede Strategie mit deterministischen Inputs, YAML-Loader, CLI
- [ ] `make lint`, `make test`, `make smoke` gruen
- [ ] Conventional Commits, einer pro Story (oder pro Sub-Schritt)
- [ ] `docs/STATE.md` aktualisiert, Tag `p2-strategies` gesetzt
- [ ] UML-Diagramme fuer jede Strategie sind APPROVED (Structure + Flow + Sequence)