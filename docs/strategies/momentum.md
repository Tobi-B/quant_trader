# Momentum 12-1 (Cross-Sectional)

Cross-Sectional Momentum-Strategie auf Basis von 12-Monats-Renditen,
ohne den letzten Monat.

## Was?

Cross-Sectional: am Ende jedes Monats (erster Bar des neuen Monats)
werden die Top-N-Performer eines Ticker-Universums nach ihrer
12-Monats-Rendite (ohne den letzten Monat) bestimmt. Diese Top-N werden
neu gewichtet (BUY fuer neue Entrants), alle anderen Positionen des
Portfolios werden verkauft.

Der "Skip-Recent-Month" (default 1 Monat) ist eine klassische
Robustheits-Massnahme aus dem akademischen Momentum-Research: der
Monatsumsatz verhaelt sich kurzfristig oft mean-reverting und wuerde
die Signale verrauschen.

## Wann BUY / Wann SELL?

- **BUY**: ein Ticker steigt in den Top-N-Bereich ein, war vorher aber
  nicht im Portfolio.
- **SELL**: ein Ticker faellt aus den Top-N heraus, war aber im
  Portfolio (egal ob er noch positive Rendite hat oder nicht).
- **HOLD**: keine Top-N-Veraenderung am Rebalancing-Tag, oder noch im
  Warmup.

Rebalancing-Frequenz ist `monthly` (ausschliesslich). In den ersten
`lookback_months + skip_recent_months` Monaten (Warmup) liefert die
Strategie keine Signale, weil nicht fuer alle Ticker genug Historie
vorliegt.

## Parameter

| Parameter            | Default | Bedeutung |
|----------------------|---------|-----------|
| `lookback_months`    | 12      | Wie viele Monate Rueckblick fuer die Momentum-Berechnung. |
| `skip_recent_months` | 1       | Wie viele der juengsten Monate ignoriert werden (typisch 1). |
| `top_n`              | 10      | Anzahl der Top-Performer, die gehalten werden sollen. |
| `rebalance_freq`     | "monthly" | Nur "monthly" ist implementiert. |

Default-Universe wird vom Aufrufer (z.B. Backtest-Orchestrator)
geliefert. Die Strategie ist multi-ticker und erwartet einen Ticker-
Pool pro Bar. Signal-Reason `momentum_entered_top_n` (BUY) bzw.
`momentum_dropped_from_top_n` (SELL).

## Risiken

- **Momentum-Crashs**: in ploetzlichen Regime-Wechseln (z.B. Crash
  nach langem Aufwaertstrend) verlieren alle Top-Performer gleichzeitig,
  und die Strategie haelt sie trotzdem, bis das naechste Rebalancing
  kommt.
- **Whipsaws bei Markt-Regime-Wechsel**: Seitwaerts- oder
  Crash-Phasen fuehren zu vielen taeglichen Rang-Verschiebungen und
  damit hoher Turnover.
- **Turnover-Kosten**: monatliches Rebalancing der kompletten
  Top-N-Position erzeugt relativ viele Trades, die im Backtest
  Slippage und Commission bezahlen.
- **Survivorship-Bias**: das Universum muss konsistent definiert sein,
  sonst werden Ticker mit guter Historie systematisch bevoorzugt.

## Beispiel-Signal

Angenommen das Universum besteht aus 30 Aktien. Am Monatsende werden
die 12-Monats-Renditen (ohne den letzten Monat) berechnet und absteigend
sortiert. Die oberen 10 sind die neuen Zielpositionen. Ticker, die im
Portfolio waren, aber nicht mehr in den Top-10 sind, erhalten ein
SELL-Signal. Ticker, die neu in den Top-10 sind, erhalten ein
BUY-Signal. Ticker ausserhalb der Top-10 ohne aktuelle Position
erhalten kein Signal.