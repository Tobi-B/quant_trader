# SMA-Cross (Simple Moving Average Crossover)

Klassische Trendfolge-Strategie auf Basis zweier Simple Moving Averages.

## Was?

Trivial-Trendfolge: BUY wenn der schnelle SMA den langsamen SMA von unten
nach oben kreuzt, SELL bei Gegenkreuzung. Die Strategie reagiert damit
rein auf Trendwendepunkte und liegt in der Mitte zwischen "Buy-and-Hold"
und kurzfristigem Trading.

Die beiden gleitenden Durchschnitte werden auf Schlusskursen berechnet
(arithmetisches Mittel). Ein Signal entsteht nur, wenn sich die relative
Position der beiden MAs zur vorherigen Bar **aendert** - reine
Nulldurchgaenge ohne Vorzeichen-Wechsel werden nicht emittiert.

## Wann BUY / Wann SELL?

- **BUY**: schneller SMA kreuzt den langsamen SMA von unten nach oben
  (vorher: `fast <= slow`, jetzt: `fast > slow`).
- **SELL**: schneller SMA kreuzt den langsamen SMA von oben nach unten
  (vorher: `fast >= slow`, jetzt: `fast < slow`).
- **HOLD**: keine Kreuzung oder noch im Warmup.

Waehrend der ersten `slow` Bars (Warmup) liefert die Strategie bewusst
keine Signale, weil der langsamere SMA noch keinen vollstaendigen
Berechnungszeitraum hat.

## Parameter

| Parameter | Default | Bedeutung |
|-----------|---------|-----------|
| `fast`    | 20      | Fenster fuer den schnellen SMA (Anzahl Schlusskurse). |
| `slow`    | 50      | Fenster fuer den langsamen SMA (muss > `fast` sein). |

Konstruktor-Parameter `ticker` ist obligatorisch, weil die Strategie
single-ticker-basiert arbeitet. Die Signal-Reason lautet
`sma_cross_up` (BUY) bzw. `sma_cross_down` (SELL).

## Risiken

- **Whipsaws** in Seitwaerts-Maerkten: schnelle SMA-Kreuzungen ohne
  echten Trend fuehren zu False-Signals und Verlusten durch die
  Roundtrip-Kosten.
- **Lag**: die Strategie reagiert verzoegert auf echte Trend-Bruche,
  weil ein SMA ueber viele Bars gemittelt wird. Ein Teil der
  Trendbewegung ist beim Entry bereits verstrichen.
- **Kein Risk-Management**: die Strategie enthaelt keinen Stop-Loss
  und keine Positionsgroessen-Steuerung. Backtest- und
  Live-Layer muessen das selbst beisteuern.
- **Parameter-Sensitivitaet**: kurze Fenster (z.B. 5/10) reagieren
  sehr unruhig, lange Fenster (z.B. 50/200) sind träge und verlieren
  Phasen.

## Beispiel-Signal

Bei einer Aktie mit aufwaerts gerichtetem Trend steigt der schnelle
20-Tage-SMA zuerst und kreuzt dann den 50-Tage-SMA von unten nach
oben. Beim Kreuzungs-Bar emittiert die Strategie ein BUY-Signal mit
`reason="sma_cross_up"`. Wenn spaeter der 20-Tage-SMA wieder unter
den 50-Tage-SMA faellt, kommt das passende SELL-Signal mit
`reason="sma_cross_down"`. In einer Seitwaerts-Phase oszillieren beide
MAs eng umeinander, es entstehen viele schnelle BUY/SELL-Folgen - das
ist der typische Whipsaw-Fall.