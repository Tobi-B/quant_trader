# RSI Mean-Reversion

Mean-Reversion-Strategie auf Basis des Relative-Strength-Index (RSI).

## Was?

Mean-Reversion-Ansatz: BUY wenn der RSI (default 14) unter die
Oversold-Schwelle (default 30) faellt, SELL bei Uebersteigen der
Overbought-Schwelle (default 70). Die Strategie setzt darauf, dass
stark gefallene Kurse (RSI < 30) kurzfristig zurueckspringen und
stark gestiegene Kurse (RSI > 70) wieder abgeben.

Verwendet wird die simple-average RSI-Variante (arithmetisches Mittel
der Gains und Losses), nicht die von Wilder urspruenglich
vorgeschlagene exponentiell-geglettete Variante (Cutler).

## Wann BUY / Wann SELL?

- **BUY**: RSI faellt unter die Oversold-Schwelle (vorher: `>=`, jetzt:
  `<` oversold).
- **SELL**: RSI steigt ueber die Overbought-Schwelle (vorher: `<=`,
  jetzt: `>` overbought).
- **HOLD**: RSI liegt zwischen den Schwellen, oder es findet kein
  Crossing statt.

Signale werden **nur bei Crossings** emittiert, nicht bei statischem
Verweilen unter/ueber der Schwelle. Waehrend der ersten `period + 1`
Bars (Warmup) liefert die Strategie keine Signale.

## Parameter

| Parameter    | Default | Bedeutung |
|--------------|---------|-----------|
| `period`     | 14      | Berechnungsfenster fuer den RSI (Anzahl Schlusskurse). |
| `oversold`   | 30.0    | Untere Schwelle; BUY-Signal bei Crossing nach unten. |
| `overbought` | 70.0    | Obere Schwelle; SELL-Signal bei Crossing nach oben. |

Konstruktor-Parameter `ticker` ist obligatorisch (single-ticker).
Signal-Reason `rsi_oversold_cross` (BUY) bzw. `rsi_overbought_cross`
(SELL).

## Risiken

- **Fail in starken Trends**: in einem starken Aufwaertstrend bleibt
  der RSI lange ueberkauft (> 70) und liefert immer wieder
  SELL-Signale, die der Trend nicht honoriert. In einem starken
  Abwaertstrend bleibt der RSI lange ueberverkauft (< 30) und immer
  neue BUY-Signale fangen Falling Knives.
- **Nicht fuer trendstarke Aktien geeignet**: High-Momentum- oder
  Growth-Titel verletzen die Mean-Reversion-Annahme regelmaessig.
- **Kurze Perioden verrauschen**: sehr kurze `period`-Werte (z.B. 5)
  erzeugen viele False-Signals, ohne die Trefferquote zu verbessern.
- **Kein Trend-Filter**: die Strategie kombiniert keine Trend- oder
  Volatility-Information und ist in trendstarken Phasen blind.

## Beispiel-Signal

Nach einem scharfen Kurseinbruch faellt der 14-Tage-RSI unter 30. Beim
Crossing-Bar emittiert die Strategie ein BUY-Signal mit
`reason="rsi_oversold_cross"`. Wenn der Kurs daraufhin tatsaechlich
zurueckspringt und der RSI spaeter die 70 ueberschreitet, kommt das
passende SELL-Signal mit `reason="rsi_overbought_cross"`. In einem
Trendmarkt hingegen bleibt der RSI dauerhaft > 70 und produziert
fruehzeitige SELL-Signale - das ist das klassische Anti-Pattern
dieser Strategie.