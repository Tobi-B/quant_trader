# ADR 0019: Instrumentkatalog aus freien Boersenquellen statt FMP

Status:     accepted
Datum:      2026-08-28
Phase:      P1 Datenlayer (Slice 1.7, Nachbesserung)
Supersedes: -
Superseded by: -
Aendert:    ADR-0018 (Abschnitte 1, 5 und 7)

## Context

ADR-0018 hat den Instrumentkatalog auf die FMP-Listen-Endpoints
(`/stable/stock-list`, `/stable/etf-list`, `/stable/*-constituent` etc.)
gestuetzt, mit der ausdruecklichen Annahme "Free-Tier verfuegbar fuer die
gelisteten Endpoints".

Diese Annahme ist fuer den tatsaechlich konfigurierten Account falsch. Bei
der manuellen Verifikation von Slice 1.7 gegen die Live-API lieferten
**alle** neuen Katalog-Endpoints `HTTP 402 Restricted Endpoint: This
endpoint is not available under your current subscription`:

- `stock-list`, `etf-list`, `available-sectors`, `available-exchanges`
- `sp500-constituent`, `nasdaq-constituent`, `dowjones-constituent`

Betroffen sind ausschliesslich die Katalog-Endpoints. Die in Slice 1.5 und
3.7 genutzten Endpoints (`historical-price-eod/full`, `search-name`,
`profile`) funktionieren unveraendert; Bar-Fetch und Unternehmenssuche sind
nicht betroffen.

Damit war der Katalog aus Slice 1.7 zwar korrekt implementiert (Fallback und
Fehlerbehandlung greifen sauber), aber ohne Plan-Upgrade dauerhaft leer.

Zusaetzlich hat die Recherche zwei Dinge gezeigt, die ADR-0018 anders
eingeschaetzt hatte:

- Die Deutsche Boerse veroeffentlicht taeglich eine vollstaendige
  Xetra-Instrumentliste **mit** Index-Handelsgruppen (`DAX1`, `MDX1`,
  `SDX1`). ADR-0018 hatte `dax40` statisch gelassen, weil "FMP keine
  DAX-Constituents-Liste dokumentiert" - die Aussage stimmt fuer FMP, aber
  die Schlussfolgerung "also statisch" war voreilig.
- Die NASDAQ-Trader-Symboldatei fuehrt Gattungsaktien in Punktschreibweise
  (`BRK.B`) - genau die Form, die US-P1.10 woertlich als Akzeptanzkriterium
  verlangt und an der die FMP-Suche urspruenglich gescheitert war.

## Decision

### 1. Katalogquelle wechselt auf schluesselfreie Boersenquellen

Neues Modul `src/quant_trader/data/public_catalog.py` mit drei Quellen und
einem Komposit-Provider, der weiterhin das bestehende
`CatalogProvider`-Protocol erfuellt - `InstrumentCatalogService`,
`InstrumentCatalogSnapshotStore` und `DynamicUniverseStore` bleiben
unveraendert.

| Quelle | Modul | Deckt ab | Gemessen 2026-08-28 |
|---|---|---|---|
| NASDAQ Trader Symbol Directory | `NasdaqTraderSource` | US-Aktien + ETFs | 13.141 |
| Deutsche Boerse Xetra | `XetraSource` | EU-Aktien, ETFs, ETNs, ETCs, Indexgruppen | 5.099 |
| CoinGecko | `CoinGeckoSource` | Kryptowaehrungen (Top-N nach Marktkapitalisierung) | 250 |

Gesamt nach Deduplizierung: **18.488 Instrumente**.

Alle drei sind HTTP-GETs ohne API-Key und werden von ihren Herausgebern
taeglich aktualisiert. Der Katalog-Refresh verbraucht damit **null** Calls
aus dem FMP-Budget (NFR-Data-3 entlastet statt belastet).

Begruendung gegen die Alternativen:
- **FMP-Plan-Upgrade**: kostet Geld fuer Daten, die es umsonst gibt, und
  macht den Katalog von einer einzelnen kommerziellen Quelle abhaengig.
- **Alpha Vantage `LISTING_STATUS`**: funktioniert mit dem vorhandenen Key
  (getestet: 8.609 Aktien + 5.780 ETFs), fuehrt Gattungsaktien aber als
  `BRK-B` statt `BRK.B` und deckt kein EU ab. Als Anreicherungsquelle
  (IPO-/Delisting-Datum) spaeter nachruestbar, nicht als Primaerquelle.
- **StockData.org**: der hinterlegte Token liefert `HTTP 401
  invalid_api_token`; die Quelle ist unabhaengig von diesem Slice defekt
  (siehe Consequences).

### 2. Fehlertoleranz zwischen den Quellen

`PublicCatalogProvider` behandelt den Ausfall einer einzelnen Quelle nicht
als Refresh-Fehler: die uebrigen Quellen ergeben weiterhin einen nutzbaren
Katalog, der Ausfall wird als `catalog.source.failed` geloggt. Erst wenn
**alle** Quellen ausfallen, wird `ProviderError` geworfen - dann greift die
bestehende Snapshot-Fallback-Logik aus ADR-0018.

Begruendung: ein Xetra-Ausfall darf nicht dazu fuehren, dass auch die
US-Instrumente verschwinden.

### 3. Ticker-Normalisierung fuer Gattungsaktien

`InstrumentCatalogService.search` vergleicht zusaetzlich gegen einen
separator-normalisierten Ticker (`-` -> `.`). Damit findet sowohl `BRK.B`
als auch `BRK-B` dasselbe Instrument, unabhaengig davon, welche Schreibweise
die Quelle oder der Trader verwendet.

### 4. Standard-Universen: `dax40` wird dynamisch, `sp500` bleibt statisch

Das dreht die Festlegung aus ADR-0018 Abschnitt 5 um:

- **`dax40` dynamisch** aus der Xetra-Handelsgruppe `DAX1`. Ehrliche
  Einschraenkung: die Gruppe enthaelt 43 statt 40 Eintraege, weil sie bei
  Commerzbank, Henkel und Volkswagen beide Aktiengattungen fuehrt
  (`CBK`/`CBK0`, `HEN`/`HEN3`, `VOW`/`VOW3`), waehrend der Index je nur eine
  verwendet. Die UI weist darauf hin. Eine Handelsgruppe ist keine
  Indexmitgliedschaft - das wird benannt statt kaschiert.
- **`etfs` dynamisch** aus `instrument_type in (etf, etn, etc)`.
- **`sp500` bleibt statisch** in `config/universe_presets.yaml`. Die
  S&P-500-Zusammensetzung ist ein lizenziertes Indexprodukt und in keiner
  schluesselfreien Quelle enthalten; FMPs Constituent-Endpoints sind auf dem
  aktuellen Plan gesperrt. Das ist eine ehrliche Luecke, keine versprochene
  Dynamik, die nicht haelt.

### 5. Memoisierung innerhalb eines Refresh

Ein Refresh ruft `fetch_stock_list`, `fetch_etf_list` und
`fetch_crypto_list` nacheinander auf. Ohne Zwischenspeicher wuerde jeder
dieser Aufrufe alle drei Quellen erneut herunterladen (gemessen: dreifacher
Download, ~5s statt ~3s). `PublicCatalogProvider` haelt die Rohdaten daher
pro Refresh im Speicher; `InstrumentCatalogService.refresh` ruft vorher
`invalidate()`, damit ein Refresh die Quellen wirklich neu liest und nicht
den letzten Lauf wiederholt.

## Consequences

**Positiv**

- Der Katalog funktioniert ohne Plan-Upgrade und ohne API-Key.
- `BRK.B` wird in Punkt- und Bindestrichschreibweise gefunden (US-P1.10).
- `dax40` ist dynamisch statt handgepflegt (US-P1.12 besser erfuellt als
  urspruenglich geplant).
- Kein Verbrauch des FMP-Free-Tier-Budgets durch den Katalog.
- Ausfall einer Quelle degradiert den Katalog, statt ihn zu blockieren.

**Negativ**

- Drei Quellen statt einer bedeuten drei Parser und drei Formate, die sich
  unabhaengig aendern koennen. Die Tests pruefen die Formate strukturtreu
  (Trennzeichen, Kopf- und Trailerzeilen), damit ein Formatwechsel als
  Testfehler auffaellt und nicht als stiller Datenverlust.
- Die Xetra-URL enthaelt einen Blob-Hash und kann sich bei einem
  Relaunch der Seite aendern. Faellt sie aus, verliert der Katalog die
  EU-Instrumente und `dax40`, nicht aber den US-Teil.
- Fonds bleiben unabgedeckt (wie schon in ADR-0018, jetzt aus anderem
  Grund: keine der freien Quellen fuehrt Publikumsfonds).
- Indexinstrumente (`^GDAXI` o.ae.) sind nicht enthalten, weil die Quellen
  handelbare Listings fuehren, keine Indexstaende. `fetch_index_list`
  liefert deshalb eine leere Liste.

**Neutral**

- `FinancialModellingPrepProvider` behaelt seine Katalog-Methoden samt
  Tests. Sie sind derzeit nicht verdrahtet, funktionieren aber sofort, falls
  der Plan spaeter aufgeruestet wird - der Wechsel waere eine Zeile in
  `_build_services()` bzw. `_build_catalog_service()`.
- Die Snapshot-, Universe- und Dashboard-Schichten aus ADR-0018 bleiben
  unveraendert; der Wechsel betrifft nur die Quellenschicht.

**Separater Befund (nicht Teil dieses Slice)**

`STOCKDATA_API_TOKEN` liefert `HTTP 401 invalid_api_token`. Der
`StockDataProvider` haengt seit Slice 1.5 als dritter Fallback in der
Bar-Fetch-Kette und ist damit faktisch wirkungslos; es faellt nur nicht auf,
weil FMP und yfinance vorher greifen. Sollte in einem eigenen Slice
behoben oder der Provider entfernt werden.

## References

- `src/quant_trader/data/public_catalog.py` (NEU)
- `src/quant_trader/data/instrument_catalog.py` (Normalisierung, Standard-Universen)
- `scripts/backtest_dashboard.py` (`_build_services`, Standard-Universen-Buttons)
- `src/quant_trader/universe/cli.py` (`_build_catalog_service`)
- `tests/data/test_public_catalog.py` (NEU, 32 Tests)
- ADR-0018 (Instrumentkatalog, Abschnitte 1/5/7 werden hier geaendert)
- ADR-0009 (FMP als Primary fuer Bars - unveraendert gueltig)
- ADR-0017 (Company Search via FMP - unveraendert gueltig)
- NFR-Data-3 (FMP Free-Tier-Budget), NFR-Data-4 (taeglicher Katalog)
