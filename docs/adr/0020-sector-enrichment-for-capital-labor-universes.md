# ADR 0020: Sektor-Anreicherung fuer Capital/Labor-Universen

Status:     accepted
Datum:      2026-09-18
Phase:      P1 Datenlayer (Erweiterung)
Supersedes: -
Superseded by: -
Ergaenzt:   ADR-0019 (freie Katalogquellen)

## Context

`long_capital_short_labor` (Slice 2.7) handelt den Spread zwischen zwei
Koerben: kapitalintensive Sektoren long, arbeitsintensive Sektoren short.
Beide Koerbe sind bisher als je vier fest verdrahtete ETF-Ticker in
`config/strategies.yaml` gepflegt (`QQQ/SPY/VNQ/JPM` gegen
`XRT/XLI/IYT/JETS`). Der Nutzerwunsch: die Strategie soll aus allen
verfuegbaren Tickern die passenden selbst auswaehlen, statt eine
handgepflegte Liste zu verwenden.

Dafuer fehlt genau ein Datum: eine Sektorzuordnung pro Aktie. Die
Katalogquellen aus ADR-0019 liefern sie nicht:

- **NASDAQ Trader** (~13.100 US-Instrumente): kein Sektorfeld im
  Dateiformat.
- **Xetra** (~5.100 EU-Instrumente): die Spalte
  `Product Assignment Group Description` ist eine Handelsgruppe der
  Boerse ("DAX", "DEUTSCHLAND", "EXCHANGE TRADED FUNDS - PASSIV"), kein
  GICS-Sektor.
- **CoinGecko**: fuer Kryptowaehrungen nicht anwendbar.

Live gegen den konfigurierten FMP-Plan geprueft (2026-09-18):

| Endpoint | Ergebnis |
|---|---|
| `/stable/profile?symbol=AAPL` | **HTTP 200**, enthaelt `sector: "Technology"` und `industry` |
| `/stable/profile-bulk` | HTTP 402 Restricted Endpoint |
| `/stable/company-screener` | HTTP 402 Restricted Endpoint |
| `/stable/stock-list` | HTTP 402 Restricted Endpoint |
| `/stable/sector-performance-snapshot` | HTTP 200, aber nur Sektor-Aggregate ohne Ticker-Zuordnung |

Verfuegbar ist also ausschliesslich der **Pro-Symbol-Endpoint**. Bei
NFR-Data-3 (250 Calls/Tag im Free-Tier) und ~13.100 US-Aktien ist eine
Vollanreicherung in einem Lauf ausgeschlossen; sie teilt sich das Budget
zudem mit Bar-Fetch und Unternehmenssuche, die denselben Key nutzen.

## Decision

### 1. Gepacter, wiederaufnehmbarer Backfill statt Einmal-Import

Sektoren aendern sich praktisch nie (Apple bleibt "Technology"). Die
Anreicherung ist deshalb ein **einmaliger, unterbrechbarer Backfill**,
kein wiederkehrender Refresh:

- `SectorEnrichmentStore` (`data/catalog/sector_enrichment.parquet`,
  Spalten `ticker, sector, industry, fetched_at`) persistiert jeden
  bereits nachgeschlagenen Ticker, atomar via `temp + os.replace` wie der
  Katalog-Snapshot selbst.
- `SectorEnrichmentService.enrich_next(limit=N)` nimmt die naechsten N
  noch nicht nachgeschlagenen US-Aktien aus dem aktuellen Snapshot, ruft
  `/stable/profile` je Ticker und schreibt das Ergebnis weg.
- Ein Ticker ohne Sektor im Profil wird **mit leerem Sektor gespeichert**,
  damit er nicht bei jedem Lauf erneut Budget kostet.
- `RateLimitedError` bricht den Lauf sofort ab, behaelt aber den bis
  dahin erzielten Fortschritt; `ProviderError` ueberspringt nur den
  einzelnen Ticker, der dann im naechsten Lauf erneut drankommt.

Getrennte Datei statt einer zusaetzlichen Spalte im Katalog-Snapshot:
der Snapshot wird bei jedem Refresh komplett neu geschrieben, die
Anreicherung soll das ueberleben.

### 2. Nur US-Aktien

FMPs Symbol-Lookup ist US-zentrisch. Ein Xetra-Mnemonic wie `SAP` wuerde
auf das US-gelistete ADR aufgeloest, nicht auf die Frankfurter Linie, und
damit eine falsche Zuordnung erzeugen. EU-Zeilen behalten deshalb ihren
Xetra-Gruppenwert.

### 3. Merge beim Lesen, nie Ueberschreiben

`InstrumentCatalogService` bekommt eine optionale `sector_source`
(Protocol `SectorSource`, erfuellt von `SectorEnrichmentStore`). In
`_require_snapshot()` werden ausschliesslich **leere** Sektorfelder
gefuellt. Damit profitieren `search()`, `list_filter_options()` und die
Universe-Builder automatisch, ohne dass der Snapshot neu geschrieben
werden muss, und die Xetra-Gruppen bleiben unangetastet.

### 4. `capital` und `labor` als Standard-Universen

Beide kommen zu `dax40`/`etfs` in `_STANDARD_UNIVERSE_NAMES` dazu und
werden ueber `build_standard_universe(name)` in den
`DynamicUniverseStore` geschrieben - damit sind sie im Katalog-Tab und
ueber `universe list` sichtbar und pruefbar wie jedes andere Universe.

Sektor-Zuordnung (vom Nutzer bestaetigt, FMP-Taxonomie):

| Basket | Sektoren |
|---|---|
| `capital` | Financial Services, Real Estate, Technology |
| `labor` | Consumer Cyclical, Industrials |

Gefiltert wird auf `instrument_type == "stock"`, Vergleich
case-insensitive. Solange keine Sektoren angereichert sind, sind beide
Koerbe leer und `build_standard_universe` wirft
`EmptyUniverseSelectionError` - ein leeres Universe wird nie gespeichert.

### 5. On-Demand gebaut, nicht zur Laufzeit aufgeloest

Die Strategie selbst bleibt unveraendert: sie liest weiterhin
`long_universe`/`short_universe` aus `config/strategies.yaml`. Die
Alternative - Aufloesung bei jedem Backtest-Lauf - haette eine neue
Abhaengigkeit vom `InstrumentCatalogService` im `BacktestOrchestrator`
und einen Parameter-Override-Hook in `StrategyLoader.load()` erfordert,
also Aenderungen an Konstruktor-Signaturen, die CLI, Dashboard und rund
20 Tests nutzen. Das Kosten-Nutzen-Verhaeltnis traegt das nicht:
Sektorzuordnungen aendern sich selten, ein Neubau auf Knopfdruck reicht.

Strategien bleiben damit rein und deterministisch (kein I/O im
Konstruktor) - konsistent mit ADR-0007/0008.

## Consequences

**Positiv**

- Der Katalog bekommt echte GICS-nahe Sektoren fuer US-Aktien, nutzbar
  fuer Suche und Filter im Dashboard, nicht nur fuer diese eine Strategie.
- `capital`/`labor` sind sichtbare, versionierte Universen statt
  unsichtbarer YAML-Listen.
- Der Backfill ist jederzeit unterbrechbar und wiederaufnehmbar; ein
  Abbruch kostet keinen Fortschritt.
- Kein Architektur-Eingriff in Orchestrator, Loader oder Strategie.

**Negativ**

- Vollanreicherung dauert bei `sector_enrichment_daily_limit = 80` rund
  **5-6 Monate** fuer alle ~13.100 US-Aktien. Bis dahin sind die
  Sektorfilter und die beiden Koerbe unvollstaendig - sie enthalten nur,
  was bereits nachgeschlagen wurde.
- Die Koerbe sind eine Momentaufnahme: nach weiterer Anreicherung muss
  `build-universe` erneut laufen, und die Ticker muessen manuell nach
  `strategies.yaml` uebernommen werden, damit die Strategie sie nutzt.
- Ein Sektorwechsel eines Unternehmens wird nie bemerkt (kein
  Re-Fetch-Mechanismus). Bewusst in Kauf genommen; ein Loeschen der
  Parquet-Datei erzwingt einen kompletten Neuaufbau.
- EU-Aktien bleiben ohne echten Sektor und damit aus beiden Koerben
  draussen.

**Neutral**

- `Settings` waechst um `sector_enrichment_path` und
  `sector_enrichment_daily_limit`.
- `SectorProfile` kommt als frozen Dataclass in `core/types.py` dazu.

## Alternatives Considered

- **Namens-Keyword-Heuristik** ("BANK", "RETAIL" im Firmennamen):
  abgelehnt. Die meisten Firmennamen nennen ihren Sektor nicht ("Apple
  Inc."), das Ergebnis waere willkuerlich und wuerde eine Praezision
  vortaeuschen, die nicht existiert.
- **Nur Sektor-ETFs statt Einzelaktien**: deutlich schneller umsetzbar
  (ein kleiner, bekannter Satz ETFs), aber es bleibt bei Proxies -
  genau das, was der Nutzerwunsch ersetzen sollte.
- **FMP-Plan-Upgrade fuer `profile-bulk`/`company-screener`**: loest das
  Budgetproblem sofort, wurde aber nicht gewaehlt, weil der Backfill
  einmalig ist und die laufenden Kosten dauerhaft waeren.
- **Fremde Sektor-Datensaetze** (z.B. GitHub-gehostete GICS-Mappings):
  abgelehnt, weil Aktualitaet und Pflegezustand nicht verifizierbar sind.

## References

- `src/quant_trader/data/sector_enrichment.py` (NEU)
- `src/quant_trader/data/financial_modelling_prep.py`
  (`fetch_sector_profile`)
- `src/quant_trader/data/instrument_catalog.py` (`SectorSource`,
  `_apply_sector_enrichment`, `capital`/`labor`)
- `src/quant_trader/core/types.py` (`SectorProfile`)
- `src/quant_trader/core/config.py` (`sector_enrichment_path`,
  `sector_enrichment_daily_limit`)
- `src/quant_trader/universe/cli.py` (`catalog enrich-sectors`,
  `catalog build-universe`)
- `scripts/backtest_dashboard.py` (Sektor-Baskets im Katalog-Tab)
- `tests/data/test_sector_enrichment.py`, `tests/data/test_catalog_service.py`
- NFR-Data-3 (FMP Free-Tier 250 Calls/Tag)
- ADR-0019 (freie Katalogquellen), ADR-0009 (FMP als Primary)
