# ETF-Rotation (Top-N Momentum)

Cross-Sectional ETF-Rotation: monatlich die Top-N ETFs nach
N-Monats-Momentum, defensive Cash-Branch wenn keiner der ETFs positive
Rendite hat.

## Was?

ETF-Rotation: am ersten Bar jedes Monats wird die N-Monats-Rendite
(default 6) pro ETF des Universums berechnet. Die Top-N-ETFs
(default 2) werden gewaehlt. Positionen ausserhalb der Top-N werden
verkauft, neue Entrants erhalten BUY-Signale.

Wenn **keiner** der ETFs im Universum eine positive N-Monats-Rendite
hat, geht die Strategie in den defensiven Cash-Modus: alle aktuellen
ETF-Positionen werden verkauft, bis das naechste Rebalancing wieder
positive Renditen findet.

## Wann BUY / Wann SELL?

- **BUY**: ETF steigt in die Top-N ein, war vorher nicht im Portfolio.
- **SELL**: ETF faellt aus den Top-N heraus und war im Portfolio.
- **SELL (defensiv)**: kein ETF hat positive Rendite - alle aktuellen
  Holdings werden liquidiert, um in Cash zu parken.
- **HOLD**: keine Top-N-Veraenderung am Rebalancing-Tag, oder noch im
  Warmup.

In den ersten `lookback_months` Monaten (Warmup) liefert die Strategie
keine Signale, weil fuer keinen ETF genug Historie vorliegt.

## Parameter

| Parameter          | Default        | Bedeutung |
|--------------------|----------------|-----------|
| `universe`         | `["SPY","AGG","TLT","IEF"]` | Liste der ETF-Ticker, die monatlich verglichen werden. |
| `top_n`            | 2              | Anzahl der Top-Performer, die gehalten werden sollen. |
| `lookback_months`  | 6              | Momentum-Lookback in Monaten. |
| `rebalance_freq`   | "monthly"      | Nur "monthly" ist implementiert. |

Das Default-Universum ist breit diversifiziert (US-Aktien + Anleihen
verschiedener Laufzeiten), kann aber beliebig ueberschrieben werden
(z.B. nur Sektor-ETFs oder Regionen-ETFs). Signal-Reason
`etf_rotation_entered_top_n` (BUY), `etf_rotation_dropped_from_top_n`
(SELL) bzw. `etf_rotation_defensive_cash` (SELL bei 0 positiven
Renditen).

## Risiken

- **ETF-Selection-Bias**: die Auswahl des Universums bestimmt die
  Strategie-Performance. Ein schlecht gewaehltes Universum kann
  systematisch schlechte Returns liefern, ohne dass die Strategie
  selbst fehlerhaft ist.
- **Rebalancing-Frequenz**: monatliches Rebalancing ist relativ
  traege. In schnellen Regime-Wechseln kann die Strategie zu spaet
  umschichten. Haeufigeres Rebalancing erhoeht die Turnover-Kosten.
- **Defensive-Cash-Timingsfehler**: die Strategie verkauft alles,
  sobald kein ETF positive Rendite hat. Das kann bei einer nur
  kurzen Drawdown-Phase zu verpasster Erholung fuehren, weil erst
  beim naechsten Monatswechsel wieder eingestiegen wird.
- **Kein Bond-Hedge**: ohne Long-Bond-Overlay reagiert die Strategie
  in starken Bond-Crashs (z.B. 2022) nur mit reduzierter Exposure,
  nicht mit aktivem Hedge.

## Beispiel-Signal

Angenommen das Universum ist `["SPY", "AGG", "TLT", "IEF"]`. Am
Monatsende werden die 6-Monats-Renditen berechnet: SPY +5%, AGG -2%,
TLT +3%, IEF -1%. Top-2 sind SPY und TLT. Wenn das Portfolio
zusaetzlich AGG haelt, erhaelt AGG ein SELL-Signal. War SPY nicht im
Portfolio, erhaelt SPY ein BUY-Signal. TLT bleibt unverändert.

In einem Monat, in dem alle vier ETFs negative Renditen haben
(beispielsweise einer umfassenden Korrektur), emittiert die Strategie
SELL-Signale fuer alle aktuellen Holdings mit
`reason="etf_rotation_defensive_cash"` und bleibt im Cash, bis das
naechste Rebalancing wieder positive Renditen findet.