# Phase 3 - Backtest: User Story Unternehmenssuche

Phase:    P3 Backtest-Engine + Reports
Slice:    3.7 Unternehmens- und Ticker-Suche im Dashboard
Status:   APPROVED
Persona:  Tobias (privater Einsteiger-Trader)
Quelle:   Nutzeranforderung vom 2026-07-16

## US-P3.11 - Unternehmen ohne bekannten Ticker finden

- **Als** Trader ohne vollständige Tickerkenntnis
- **möchte ich** im Dashboard nach dem Namen eines Unternehmens, ETFs oder nach einem bekannten Ticker suchen und passende Instrumente auswählen können,
- **damit** ich einen Backtest starten kann, ohne das Börsenkürzel vorher kennen zu müssen.

- **INVEST:** Die Story ist unabhängig vom Backtest-Start, wertvoll für Einsteiger, auf eine Such- und Auswahlinteraktion begrenzt, schätzbar und separat testbar.
- **Priority:** Must
- **Estimate:** M
- **T-Shirt-Size:** M

## Acceptance Criteria (Gherkin)

- **Given** ich habe im Dashboard das Formular für einen eigenen Ticker geöffnet
- **When** ich einen vollständigen oder teilweisen Unternehmensnamen eingebe
- **Then** sehe ich passende Instrumente mit verständlicher Bezeichnung, Ticker und Börsenplatz

- **Given** ich kenne den Ticker bereits
- **When** ich den Ticker in das Suchfeld eingebe
- **Then** wird das passende Instrument ebenfalls gefunden

- **Given** mehrere Instrumente passen zu meiner Suche
- **When** ich die Ergebnisliste öffne
- **Then** kann ich anhand von Name, Ticker und Börsenplatz das gewünschte Instrument eindeutig auswählen

- **Given** ich habe ein Suchergebnis ausgewählt
- **When** die Auswahl übernommen wird
- **Then** steht der zugehörige Ticker im Backtest-Formular und kann direkt für den Backtest verwendet werden

- **Given** meine Suche liefert keine Treffer
- **When** die Suche abgeschlossen ist
- **Then** sehe ich eine klare deutsche Meldung und kann die Suchanfrage ändern

- **Given** die Unternehmenssuche ist vorübergehend nicht verfügbar
- **When** ich eine Suche ausführe
- **Then** bleibt das Backtest-Formular benutzbar und ich sehe eine klare deutsche Fehlermeldung

- **Given** ich habe ein Universe-Preset ausgewählt
- **When** ich das Formular bearbeite
- **Then** wird die Unternehmenssuche nicht benötigt und das gewählte Universe bleibt unverändert

## MoSCoW

- **Must:** Suche nach Unternehmensname und Ticker; Anzeige von Name, Ticker und Börsenplatz; Auswahl übernimmt den Ticker; deutsche Meldungen bei keinen Treffern und bei nicht verfügbarer Suche.
- **Should:** Teilwortsuche und tolerante Groß-/Kleinschreibung.
- **Could:** Filter nach Börsenplatz oder Land.
- **Won't:** Orderaufgabe, Anlageberatung oder automatische Auswahl eines Treffers ohne Nutzerbestätigung.

## Mapped NFRs

- NFR-Ux-1: Deutsche UI-Texte und klare, actionable Fehlermeldungen.
- NFR-Data-1: Auswahl und anschließender Backtest verwenden weiterhin den bestehenden Daten- und Cachepfad.
