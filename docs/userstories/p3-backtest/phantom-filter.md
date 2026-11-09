# Phase 3 - Backtest: User Story Phantom-Ticker-Filter

Phase:    P3 Backtest-Engine + Reports
Slice:    3.8 Phantom-Ticker-Filter in der Suche
Status:   APPROVED
Persona:  Tobias (privater Einsteiger-Trader)
Quelle:   Nutzeranforderung vom 2026-07-18 (Folgeslice zu 3.7)

## Kontext

Die FMP-Suche (`/stable/search-name`) liefert fuer bekannte Unternehmen wie
"Apple Inc." auch Listings, fuer die das System keine Kurshistorie cachen
kann. Beispiel: Suche nach `apple` liefert `AAPL.DE` (XETRA) als Top-Treffer,
aber weder FMP noch YFinance halten dort tatsaechlich Daten vor
(FMP-Profil: `price: null, marketCap: 0, volume: 0`). Der Trader waehlt
solche Phantoms aus, der Backtest bricht mit `CacheMissingError` ab.

## US-P3.12 - Phantom-Ticker aus Suche ausblenden

- **Als** Trader, der ueber die Unternehmenssuche einen Custom-Ticker auswaehlt,
- **moechte ich**, dass nur Ticker in der Ergebnisliste erscheinen, fuer die das
  System auch tatsaechlich historische Kursdaten liefern kann,
- **damit** ich nicht in eine `CacheMissingError`-Sackgasse laufe und direkt
  einen nutzbaren Ticker auswaehlen kann.

- **INVEST:** Die Story ist unabhaengig vom Backtest-Start, wertvoll fuer jeden
  Custom-Ticker-Workflow, auf das Filterverhalten der Suche begrenzt,
  schaetzbar und separat testbar.
- **Priority:** Must
- **Estimate:** S
- **T-Shirt-Size:** S

## Acceptance Criteria (Gherkin)

- **Given** die Suche liefert ein Ergebnis, das kein tatsaechliches Listing ist
  (Profil ohne Preis und Volumen, z.B. `AAPL.DE`)
- **When** ich die Suche ausfuehre
- **Then** erscheint dieses Ergebnis nicht in der Trefferliste

- **Given** die Suche liefert ein Ergebnis mit echten Profildaten
  (Preis und Volumen groesser 0, z.B. `APC.DE` oder `SAP.DE`)
- **When** ich die Suche ausfuehre
- **Then** erscheint dieses Ergebnis wie bisher in der Trefferliste

- **Given** die Profil-Validierung schlaegt fehl (Netzwerk, Rate-Limit)
- **When** ich die Suche ausfuehre
- **Then** werden alle FMP-Suchergebnisse ohne Filterung angezeigt
  (graceful degradation) und die Suche bleibt benutzbar

- **Given** der Trader sucht nach `apple` und der Phantom-Filter entfernt alle Treffer
- **When** die Suche abgeschlossen ist
- **Then** sieht der Trader die bestehende Meldung
  "Keine Treffer fuer '<q>'. Bitte Suchbegriff aendern."

- **Given** der Trader hat bereits ein Ergebnis uebernommen
- **When** eine neue Suche ohne Phantom-Treffer laeuft
- **Then** bleibt der bereits uebernommene Ticker unveraendert im Formular

## MoSCoW

- **Must:** Phantom-Treffer ausblenden (basierend auf FMP-Profil
  `price is None` oder `volume == 0`); graceful degradation bei
  Validator-Fehler; bestehende deutsche UI-Texte und Fehlermeldungen
  unveraendert.
- **Should:** Strukturiertes Logging der herausgefilterten Treffer
  (`instrument.search.phantom_filtered`).
- **Could:** Konfigurierbarer Validator (z.B. YFinance-Validator als
  Alternative).
- **Won't:** Phantom-Detection in der Daten-Fallback-Kette, andere
  Such-Provider umstellen, harte Symbol-Blacklist pflegen.

## Mapped NFRs

- NFR-Data-1: Cache-Pfad und Fallback-Kette bleiben unveraendert;
  Filter wirkt ausschliesslich auf das Suchergebnis.
- NFR-Sec-1: API-Key kommt ausschliesslich aus `.env` (FMP-Key),
  kein zusaetzlicher Credential.
- NFR-Obs-1: Strukturiertes Logging der Anzahl entfernter Phantom-Treffer.
- NFR-Ux-1: Keine neuen UI-Texte; bestehende "Keine Treffer"-Meldung
  deckt den leeren-Filter-Fall ab.

## Implementation-Skizze (zur Diskussion im Slice-PRD)

- `PhantomValidator` Protocol in `src/quant_trader/data/instrument_search.py`
  mit `is_real(symbol: str) -> bool`.
- `FmpProfilePhantomValidator` im gleichen Modul, ruft
  `/stable/profile?symbol=...` fuer jedes Suchergebnis und verwirft
  Treffer mit `price is None` oder `volume == 0`.
- `CompanySearchService` akzeptiert optional `phantom_validator`. Wenn
  gesetzt, werden Ergebnisse nach der Provider-Antwort gefiltert;
  Validator-Ausnahmen werden geloggt und das Ergebnis ungefiltert
  durchgereicht.
- Dashboard-Wiring in `scripts/backtest_dashboard.py:_build_services()`
  uebergibt den neuen Validator an `CompanySearchService`.
- Tests mit Fake-Validator in `tests/data/test_instrument_search.py`.
