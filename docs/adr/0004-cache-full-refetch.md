# ADR 0004: Cache-Strategie: Full-Refetch statt Inkrement-Update

Status:     accepted
Datum:      2026-07-10
Phase:      P1 (rueckwirkend dokumentiert)

## Context

NFR-Data-1 sagt: "Parquet-Cache mit Inkrement-Update (kein Full-Refetch bei Overlap)". Das ist die Wunsch-Property. Die P1.2-Implementation macht aber:

```python
if self._cache.covers(ticker, granularity, start, end):
    return CacheHit(...)
else:
    bars = self._provider.fetch(ticker, start, end, granularity)
    self._cache.write(ticker, granularity, bars)  # kompletter Replace
```

Echtes Inkrement-Update waere:
- letzten Timestamp im Cache lesen
- `provider.fetch(ticker, last_ts+1, end, granularity)` aufrufen
- neue Bars konkatenieren
- Gap-Detection (falls Provider Daten verpasst hat)

Das ist mehr State, mehr Reconciliation, mehr Test-Cases.

## Decision

**Phase 1 (akzeptiert)**: Cache-Miss = kompletter Refetch + Replace der Datei. Kein Inkrement, keine Gap-Detection. NFR-Data-1 wird in P1 als "Cache-Pfad ist deterministisch" interpretiert (siehe Slice-PRD 1.2), nicht als "Inkrement-Update implementiert".

**Phase 3+ (geplant)**: Echtes Inkrement-Update, sobald Backtest-Engine existiert und Re-Fetch-Performance relevant wird (grosse Universen × lange History).

## Consequences

**Positiv**
- Simpel, deterministisch: Cache-Inhalt ist exakt das Ergebnis des letzten Fetch
- Keine Gap-Detection noetig
- Kein "warum fehlt der 2023-04-15"-Debugging
- Tests trivial: write → read → identische Bars

**Negativ**
- Bei vorhandenem Cache + kleinem neuen Range: kompletter Refetch verschwendet Bandbreite
- AV-Quota wird bei wiederholten Fetchs der gleichen Range verbrannt (Cache deckt aber idR. ab)
- Wenn der Cache gross ist (>100MB), ist Refetch der vollen Range teuer

**Neutral**
- Idempotenz bleibt erhalten (gleicher Range-Request → gleicher Cache-Inhalt)
- `covers()`-Check macht die meisten Fetchs ueberfluessig

## Alternatives Considered

- **Echtes Inkrement in P1**: verworfen — Scope-Creep fuer P1.2, nicht noetig fuer damaligen Stand
- **Delta-Only mit Merge**: technisch moeglich, aber Reconciliation bei Schema-Mismatch komplex
- **Write-Ahead-Log (WAL)**: overkill fuer single-threaded, append-light Use-Case

## Migration Path (zukuenftig)

In Phase 3 oder spaeter:
1. `ParquetCache.append(ticker, granularity, new_bars)` als zusaetzliche Methode
2. `DataService.get()` erkennt Overlap und ruft `append()` statt `write()`
3. Gap-Detection via `pd.date_range` ueber (existing_range, requested_range)
4. ADR 0004 wird zu `superseded by 00XX-incremental-cache.md`

## References

- `src/quant_trader/data/cache.py` (`write` macht Replace)
- `src/quant_trader/data/service.py` (Cache-Miss-Pfad)
- Slice-PRD `docs/prd/p1-data/data-provider.md` (Out-of-Scope: Inkrement)
- NFR-Data-1 (APPROVED, aber in P1 als "deterministisch" interpretiert)
