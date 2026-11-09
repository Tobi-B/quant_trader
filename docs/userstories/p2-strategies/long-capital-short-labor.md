# Phase 2 - Strategien: User Story Long Capital / Short Labor

Phase:    P2 Strategien
Slice:    2.7 Long Capital / Short Labor Strategie
Status:   APPROVED
Persona:  Tobias (privater Einsteiger-Trader)
Quelle:   Nutzeranforderung vom 2026-07-18 (Folgeslice zu 2.6)

## Kontext

Die bisherigen Strategien (slice_cross, momentum, rsi_mean_reversion,
etf_rotation) operieren alle long-only oder rein sektor-rotierend.
Trader, die einen politisch-ökonomischen Ausblick haben ("Kapital
schlägt Arbeit" oder umgekehrt), benötigen ein Long/Short-Konstrukt,
das diese Sicht hedged umsetzt, ohne auf Einzelaktien-Wetten
angewiesen zu sein.

Die Strategie bildet einen paired-trade auf der "Capital vs Labor"-Achse
ab: Long-Korb enthält Kapitalallokatoren (Broad Market, Tech, Banken,
REITs), Short-Korb enthält arbeitsintensive Sektoren (Retail,
Industrials, Transport, Airlines). Das Exposure ist symmetrisch (50/50
gross) und folgt einem 6-Monats-Relative-Stärke-Signal.

## US-P2.9 - Long Capital / Short Labor als monatliches Pair

- **Als** Trader mit einem makroökonomischen Ausblick auf die
  "Capital vs Labor"-Achse
- **möchte ich** eine fertig implementierte Strategie im System, die
  monatlich einen Long-Korb (Kapitalallokatoren) gegen einen Short-Korb
  (arbeitsintensive Sektoren) handelt, gesteuert von einem
  Relative-Stärke-Signal über 6 Monate,
- **damit** ich ohne eigenen Code-Aufwand eine komplexe Long/Short-
  Strategie backtesten und später produktiv nutzen kann.

- **INVEST:** Die Story ist unabhängig von den anderen Strategien,
  wertvoll für Trader mit Branchen-Outlook, durch die monatliche
  Signal-Logik klar abgegrenzt, schätzbar und separat testbar.
- **Priority:** Should
- **Estimate:** M
- **T-Shirt-Size:** M

## Universe (Nutzerentscheidung 2026-07-18)

- **Long-Korb (Kapitalseite):** QQQ, SPY, VNQ, JPM
- **Short-Korb (Arbeitnehmerseite):** XRT, XLI, IYT, JETS

Beide Körbe sind als Default-Parameter in der Klasse hinterlegt; per
`params`-Override überschreibbar.

## Signal-Logik (Nutzerentscheidung Relative-Stärke)

- Lookback-Fenster: 6 Monate (~126 Trading-Tage)
- Berechnung pro Basket: arithmetisches Mittel der 6-Monats-Returns
  aller Korb-Ticker
- Spread = long_avg_return − short_avg_return
- **Entry** am Rebalance-Tag wenn `spread > entry_threshold` (default 0.02 = +2%):
  - BUY für jeden Long-Ticker
  - SELL für jeden Short-Ticker
- **Exit** wenn aktuell investiert UND `spread < exit_threshold` (default 0.0):
  - SELL für jeden Long-Ticker
  - BUY-to-Cover für jeden Short-Ticker
- Andernfalls: keine Aktion
- Rebalance-Frequenz: monatlich (1. Trading-Tag eines neuen Monats)

## Acceptance Criteria (Gherkin)

- **Given** die Strategie ist geladen mit Long-Korb `[QQQ, SPY, VNQ, JPM]`
  und Short-Korb `[XRT, XLI, IYT, JETS]`
- **When** am Rebalance-Tag der 6-Monats-Return des Long-Korbs
  den des Short-Korbs um +2.5 % übersteigt
- **Then** emittiert die Strategie 4 BUY-Signale (Long-Korb) und
  4 SELL-Signale (Short-Korb)

- **Given** die Strategie ist mit Long-Korb investiert und der Spread
  fällt auf −1 %
- **When** der nächste Rebalance-Tag erreicht wird
- **Then** emittiert die Strategie 4 SELL-Signale (Long-Korb schließen)
  und 4 BUY-Signale (Short-Korb schließen)

- **Given** die Strategie ist mit Long-Korb investiert und der Spread
  liegt zwischen 0 % und +2 %
- **When** der nächste Rebalance-Tag erreicht wird
- **Then** emittiert die Strategie keine neuen Signale (Hold)

- **Given** die Strategie wird auf einem Zeitraum gestartet, in dem
  ein Korb-Ticker keinen ausreichenden Verlauf für die
  6-Monats-Berechnung hat
- **When** die Warmup-Phase noch nicht abgeschlossen ist
- **Then** emittiert die Strategie keine Signale (Warmup-Log)

- **Given** ein vom Nutzer überschriebenes Universe (z.B. nur 2 Long-
  und 2 Short-Ticker)
- **When** die Strategie läuft
- **Then** arbeitet sie mit den überschriebenen Tickern ohne weitere
  Anpassungen

## MoSCoW

- **Must:** Long/Short-Korb-Management, 6-Monats-Relative-Stärke-Signal,
  Entry/Exit-Schwellen konfigurierbar, monatliche Rebalance, Warmup-Log,
  Default-Parameter mit den Nutzer-Tickern.
- **Should:** Strukturiertes Logging der Spread-Berechnung und der
  Basket-Returns pro Rebalance-Tag.
- **Could:** Eigene `params`-Overrides für jedes Basket getrennt.
- **Won't:** Einzelaktien-Selektion innerhalb eines Korbs, dynamische
  Basket-Rebalancing, Options-Hedging.

## Mapped NFRs

- NFR-Data-1: Cache-Pfad bleibt unverändert; Strategie liest Bars aus
  dem bestehenden Parquet-Cache.
- NFR-Obs-1: Strukturiertes Logging (`long_capital_short_labor.rebalance`)
  mit Spread und Basket-Returns.
- NFR-Strategy-1 (neu vorzuschlagen): Strategien liefern deterministische
  Signale bei gleichen Eingabebars (keine Randomness).

## Implementation-Skizze

- Neue Datei `src/quant_trader/strategies/long_capital_short_labor.py`
- Klasse `LongCapitalShortLaborStrategy(MultiTickerStrategyBase)` mit
  Self-Registration im `strategies/__init__.py`
- Default-Params in `config/strategies.yaml` unter
  `long_capital_short_labor:`
- Tests in `tests/strategies/test_long_capital_short_labor.py` mit
  deterministischen Fake-Bars
- README in `docs/strategies/long_capital_short_labor.md` analog zu
  den bestehenden Strategie-Dokumentationen
