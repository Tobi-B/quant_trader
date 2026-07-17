# Long Capital / Short Labor

Paired Long/Short-Strategie auf der "Capital vs Labor"-Achse: monatlich
wird ein Long-Korb (Kapitalallokatoren) gegen einen Short-Korb
(arbeitsintensive Sektoren) gehandelt, gesteuert von einem
6-Monats-Relative-Stärke-Signal.

## Was?

Long-Korb (Kapitalseite): QQQ (Tech), SPY (Broad Market), VNQ (REITs),
JPM (Banken). Short-Korb (Arbeitnehmerseite): XRT (Retail), XLI
(Industrials), IYT (Transport), JETS (Airlines).

Jeden Monat am ersten Bar wird die 6-Monats-Rendite jedes Korb-Tickers
berechnet, pro Korb das arithmetische Mittel gebildet und daraus der
Spread `long_avg − short_avg` ermittelt. Liegt der Spread über der
Entry-Schwelle, geht die Strategie in den Pair (Long-Korb kaufen,
Short-Korb shorten). Fällt der Spread unter die Exit-Schwelle,
schließt sie beide Beine. Dazwischen hält sie die Position.

## Wann BUY / Wann SELL?

- **BUY** (Long Entry): Spread > `entry_threshold` UND nicht investiert.
  Für jeden Long-Korb-Ticker.
- **SELL** (Short Entry): Spread > `entry_threshold` UND nicht investiert.
  Für jeden Short-Korb-Ticker.
- **SELL** (Long Exit): Investiert UND Spread < `exit_threshold`.
  Für jeden Long-Korb-Ticker.
- **BUY** (Short Cover): Investiert UND Spread < `exit_threshold`.
  Für jeden Short-Korb-Ticker.
- **HOLD**: kein Rebalancing-Tag, Warmup, oder Spread zwischen
  `exit_threshold` und `entry_threshold`.

In den ersten `lookback_months` Monaten (Warmup) liefert die Strategie
keine Signale, weil für keinen Korb-Ticker genug Historie vorliegt.

## Parameter

| Parameter          | Default                                        | Bedeutung |
|--------------------|------------------------------------------------|-----------|
| `long_universe`    | `[QQQ, SPY, VNQ, JPM]`                         | Long-Korb (Kapitalseite). |
| `short_universe`   | `[XRT, XLI, IYT, JETS]`                        | Short-Korb (Arbeitnehmerseite). |
| `lookback_months`  | 6                                              | Momentum-Lookback in Monaten. |
| `entry_threshold`  | 0.02                                           | Spread > +2 % triggert Entry. |
| `exit_threshold`   | 0.0                                            | Spread < 0 % triggert Exit. |
| `rebalance_freq`   | "monthly"                                      | Nur "monthly" implementiert. |

Der kombinierte `universe` (long + short) wird automatisch in
`params["universe"]` gespiegelt, damit der Runner die Bars aller
Korb-Ticker liest.

## Risiken

- **Basket-Konzentration**: vier Ticker pro Seite, gleichgewichtet.
  Ein einzelner Ausreißer (z.B. JPM in einer Bankenkrise) zieht den
  Korb-Return stark. Bei zu kleinem Basket steigt das
  Klumpenrisiko überproportional.
- **Relative-Stärke ist Trendfolger**: die Strategie kauft den
  Outperformer und shortet den Underperformer, in der Annahme dass
  die relative Stärke anhält. Bei scharfen Mean-Reversion-Schüben
  (z.B. plötzlicher Sektor-Rotation) verliert sie.
- **Symmetrisches Exposure (50/50)**: long und short haben gleiches
  Brutto-Gewicht. In starken Trendmärkten dominiert der Long-Korb den
  P&L, in Risk-On/Off-Phasen der Short-Korb. Keine dynamische
  Größenanpassung.
- **Rebalancing-Frequenz monatlich**: ein plötzlicher Regime-Wechsel
  in der Monatsmitte wird erst am Monatswechsel umgesetzt. Der
  Einstieg erfolgt damit tendenziell zu spät.
- **Kein Pair-Hedge jenseits der zwei Beine**: keinzelne
  Marktrisiko-Hedge (z.B. SPY-Overlay), keine
  Volatilitäts-Steuerung. Drawdown-Risiko entspricht einem
  klassischen Long/Short-Pair.
- **Sektor-Overlap**: SPY enthält bereits Industrie- und
  Konsumwerte. Der Short-Korb ist daher nicht perfekt von der
  Long-Seite isoliert. Die Spread-Bewegung wird dadurch gedämpft.

## Beispiel-Signal

Angenommen das Universum ist `[QQQ, SPY, VNQ, JPM]` long und
`[XRT, XLI, IYT, JETS]` short. Im Monatswechsel liefern die
6-Monats-Renditen z.B. Long-Korb im Mittel +6 % und Short-Korb
im Mittel +1 %. Der Spread beträgt +5 % und liegt klar über der
Entry-Schwelle von +2 %.

Die Strategie emittiert 4 BUY-Signale (QQQ, SPY, VNQ, JPM) mit
`reason="lcsl_long_entry"` und 4 SELL-Signale (XRT, XLI, IYT, JETS)
mit `reason="lcsl_short_entry"`. Im Folgemonat fällt der Spread auf
−1 %, was die Exit-Schwelle von 0 % unterschreitet: 4 SELL-Signale
(Long Exit) und 4 BUY-Signale (Short Cover) schließen die Beine.
