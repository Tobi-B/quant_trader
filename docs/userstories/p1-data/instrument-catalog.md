# Phase 1 - Datenlayer: User Stories Instrumentkatalog

Phase:    P1 Datenlayer
Slice:    1.7 Zentraler Instrumentkatalog und dynamische Universen
Status:   APPROVED
Persona:  Tobias (privater Einsteiger-Trader)
Quelle:   Nutzeranforderung vom 2026-07-19

## US-P1.10 - Vollständigen Instrumentkatalog durchsuchen

- **Als** Trader
- **möchte ich** alle bei Financial Modeling Prep verfügbaren Aktien, ETFs, Fonds, Indizes und Kryptowährungen in einem zentralen Katalog durchsuchen können,
- **damit** ich gültige Instrumente zuverlässig finde und nicht an unvollständigen Suchergebnissen oder unbekannten Tickern scheitere.

- **INVEST:** Die Story liefert unabhängig von der Universe-Erstellung einen nutzbaren, durchsuchbaren Instrumentbestand, hat einen klaren Anwenderwert und kann anhand repräsentativer Instrumentarten separat getestet werden.
- **Priority:** Must
- **Estimate:** L
- **T-Shirt-Size:** L

### Acceptance Criteria (Gherkin)

- **Given** Financial Modeling Prep führt Aktien, ETFs, Fonds, Indizes und Kryptowährungen
- **When** der Instrumentkatalog erfolgreich aktualisiert wurde
- **Then** kann ich Instrumente aller fünf Arten im Dashboard finden

- **Given** `BRK.B` ist im aktuellen Instrumentkatalog vorhanden
- **When** ich nach `BRK.B` suche
- **Then** wird das Instrument gefunden und nicht als unbekannt abgewiesen

- **Given** mehrere Instrumente haben ähnliche Namen oder Symbole
- **When** ich die Trefferliste öffne
- **Then** kann ich sie anhand von Name, Symbol, Instrumentart, Börse und Land unterscheiden, soweit diese Angaben verfügbar sind

- **Given** meine Suche liefert keine Treffer
- **When** die Suche abgeschlossen ist
- **Then** sehe ich eine klare deutsche Meldung und kann meine Eingabe ändern

## US-P1.11 - Universen aus dem Katalog erstellen

- **Als** Trader
- **möchte ich** Instrumente nach Index, Börse, Land, Sektor und Instrumentart filtern oder einzeln auswählen und als benanntes Universe speichern können,
- **damit** ich passende Instrumentgruppen ohne manuelle Tickerpflege in mehreren Backtests wiederverwenden kann.

- **INVEST:** Die Story nutzt den Katalog, ist aber unabhängig von dessen Aktualisierungszeitpunkt; sie erzeugt ein klar abgegrenztes, dauerhaft wiederverwendbares Ergebnis und ist pro Filter sowie Speicheraktion testbar.
- **Priority:** Must
- **Estimate:** L
- **T-Shirt-Size:** L

### Acceptance Criteria (Gherkin)

- **Given** der Instrumentkatalog enthält Instrumente aus mehreren Ländern, Börsen, Sektoren und Indizes
- **When** ich einen oder mehrere dieser Filter auswähle
- **Then** sehe ich nur die Instrumente, die alle gewählten Kriterien erfüllen

- **Given** ich möchte ein individuelles Universe erstellen
- **When** ich Instrumente aus dem Katalog einzeln auswähle
- **Then** kann ich die Auswahl vor dem Speichern prüfen und ändern

- **Given** ich habe eine gefilterte oder individuelle Auswahl erstellt
- **When** ich einen eindeutigen Namen vergebe und speichere
- **Then** steht das Universe bei späteren Dashboard-Sitzungen und Backtests unter diesem Namen zur Verfügung

- **Given** ein gleichnamiges Universe existiert bereits
- **When** ich erneut unter diesem Namen speichere
- **Then** werde ich vor dem Ersetzen eindeutig gefragt

- **Given** meine Filterkombination liefert keine Instrumente
- **When** ich das Universe speichern möchte
- **Then** wird kein leeres Universe gespeichert und ich sehe einen verständlichen Hinweis

## US-P1.12 - Standard-Universen dynamisch aktuell halten

- **Als** Trader
- **möchte ich** die bestehenden Standard-Universen wie S&P 500, DAX 40 und ETFs aus dem aktuellen Instrumentkatalog erhalten,
- **damit** Indexänderungen und gültige Symbole ohne manuelle Anpassung in meinen Backtests berücksichtigt werden.

- **INVEST:** Die Story ersetzt gezielt die Pflege bestehender Presets, liefert unmittelbar aktuellere Backtest-Auswahlen und ist anhand bekannter Aufnahme- und Entfernungsfälle separat prüfbar.
- **Priority:** Must
- **Estimate:** M
- **T-Shirt-Size:** M

### Acceptance Criteria (Gherkin)

- **Given** der aktuelle Katalog enthält die aktuelle Zusammensetzung eines Standard-Universes
- **When** ich S&P 500, DAX 40 oder ETFs auswähle
- **Then** wird das Universe aus dem aktuellen Katalog aufgebaut statt aus einer statischen Tickerliste

- **Given** ein Instrument wurde seit der letzten erfolgreichen Aktualisierung in einen Index aufgenommen oder daraus entfernt
- **When** ich das betroffene Standard-Universe nach der nächsten erfolgreichen Aktualisierung verwende
- **Then** entspricht seine Zusammensetzung dem aktualisierten Stand

- **Given** bestehende Backtests verwenden einen bekannten Namen wie `sp500`, `dax40` oder `etfs`
- **When** die dynamischen Standard-Universen eingeführt werden
- **Then** bleiben diese Namen weiterhin auswählbar

## US-P1.13 - Tägliche Aktualisierung mit verlässlichem Fallback

- **Als** Trader
- **möchte ich** den Instrumentkatalog täglich aktualisiert vorfinden und bei einem Ausfall weiterhin den letzten erfolgreichen Stand nutzen können,
- **damit** ich mit aktuellen Instrumenten arbeite, ohne dass ein vorübergehender Ausfall meine Suche oder Backtests blockiert.

- **INVEST:** Die Story beschreibt ein eigenständiges, sichtbares Aktualitäts- und Ausfallverhalten, schafft direkten Zuverlässigkeitswert und ist mit erfolgreichen sowie fehlgeschlagenen Aktualisierungen separat testbar.
- **Priority:** Must
- **Estimate:** M
- **T-Shirt-Size:** M

### Acceptance Criteria (Gherkin)

- **Given** der Katalog wurde zuletzt an einem früheren Tag erfolgreich aktualisiert
- **When** ich ihn an einem neuen Tag erstmals verwende und die Quelle erreichbar ist
- **Then** steht mir nach der Aktualisierung der neue Katalogstand zur Verfügung

- **Given** eine tägliche Aktualisierung ist bereits erfolgreich abgeschlossen
- **When** ich den Katalog am selben Tag erneut verwende
- **Then** kann ich ihn ohne eine weitere vollständige Aktualisierung nutzen

- **Given** die tägliche Aktualisierung schlägt fehl und ein früherer Katalogstand ist vorhanden
- **When** ich Instrumente suche oder ein Universe auswähle
- **Then** kann ich den letzten erfolgreichen Katalog weiterverwenden
- **And** sehe eine deutsche Warnung mit dessen Aktualisierungszeitpunkt

- **Given** die Aktualisierung schlägt fehl und es existiert noch kein erfolgreicher Katalogstand
- **When** ich den Katalog verwenden möchte
- **Then** sehe ich eine klare deutsche Meldung und es wird kein unvollständiges Universe erzeugt

## MoSCoW

- **Must:** Alle fünf Instrumentarten im FMP-Katalog; exakte Suche nach gültigen Symbolen wie `BRK.B`; Filter nach Index, Börse, Land und Sektor; individuelle Auswahl; benannte und wiederverwendbare Universen; dynamischer Ersatz der bestehenden Presets; tägliche Aktualisierung; letzter erfolgreicher Stand als Fallback.
- **Should:** Sichtbarer Aktualisierungszeitpunkt; verständliche Metadaten zur Unterscheidung ähnlicher Treffer; Bestätigung vor dem Überschreiben eines eigenen Universes.
- **Could:** Ergebnisanzahl und Sortierung der Katalogansicht; Duplizieren eines bestehenden Universes als Ausgangspunkt.
- **Won't:** Echtzeit-Aktualisierung während des Tages, automatische Anlageberatung, automatische Orderfähigkeit aller gelisteten Instrumente oder Universen aus Quellen außerhalb von Financial Modeling Prep in diesem Slice.

## Mapped NFRs

- NFR-Sec-1: Zugangsdaten bleiben außerhalb des Repositories.
- NFR-Obs-1: Aktualisierungen und die Nutzung eines älteren Katalogstands werden strukturiert protokolliert.
- NFR-Ux-1: Dashboard-Texte und Fehlermeldungen sind deutsch und handlungsorientiert.
- NFR-Data-3: Financial Modeling Prep ist die primäre Quelle.

## Definition of Done

- [x] User Stories durch den Nutzer APPROVED.
- [x] Slice-bezogene NFRs geprüft und bei Bedarf ergänzt.
- [x] Structure-, Flow- und Sequence-UML mit den Anforderungen verknüpft und APPROVED.
- [x] Gherkin-Akzeptanzkriterien als Tests umgesetzt.
- [x] `make test`, `make lint` und `make smoke` sind grün.
