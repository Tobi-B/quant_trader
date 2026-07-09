# ADR 0003: Parquet als alleinige Marktdaten-Persistenz

Status:     accepted
Datum:      2026-07-10
Phase:      P1 (rueckwirkend dokumentiert)

## Context

Marktdaten (Bars) haben folgende Charakteristika:
- **Read-heavy** (Backtest liest tausende Bars mehrfach, schreibt nur bei Fetch)
- **Append-light** (Updates sind volle Range-Refreshs, keine In-Place-Appends)
- **Spalten-orientiert lesbar** (Backtest braucht typischerweise `close`-Spalte ueber viele Bars)
- **Kein Transaktions-Bedarf** (single-threaded, kein Multi-Writer)
- **Gross** (1 Ticker × 5 Jahre daily = ~1250 Zeilen × 5 Spalten; Universe = 50+ Ticker = relevant)

Speicheroptionen: Parquet, SQLite, HDF5, CSV, In-Memory-Pandas.

## Decision

Parquet-Files pro Ticker+Granularity unter `data/raw/{granularity}/{TICKER}.parquet`, geschrieben via `pyarrow` und gelesen via `pandas.read_parquet`. Cache-Pfad: `<data_dir>/<granularity.path_segment>/<TICKER>.parquet`.

```python
class ParquetCache:
    def read(ticker, granularity, start, end) -> list[Bar]: ...
    def write(ticker, granularity, bars) -> None: ...
    def covers(ticker, granularity, start, end) -> bool: ...
    def exists(ticker, granularity) -> bool: ...
```

`granularity.path_segment` liefert `daily`/`60m`/`15m` (siehe ADR 0005). Schema ist fix: `timestamp, open, high, low, close, adjusted_close, volume`.

## Consequences

**Positiv**
- PyArrow columnar read: Backtest liest nur `close`-Spalte, ignoriert Rest
- Git-ignore: grosse Datenfiles nicht im VCS
- Idempotenz via Filename + Schema-Version (zukuenftig)
- `covers()` macht Range-Check ohne File zu laden (nur min/max timestamp)
- Tooling-Oekosystem: Parquet-Inspektoren (DBeaver, VSCode-Extensions)

**Negativ**
- Keine concurrent-write-Garantien (nicht noetig single-threaded)
- Schema-Migration ist explizit: bei Aenderung muss man Code + Files koordinieren
- Keine Query-Flexibilitaet (kein `SELECT * WHERE ticker IN (...)`)

**Neutral**
- Encoding: Parquet default (Snappy) ist schnell genug; keine GZIP noetig

## Alternatives Considered

- **SQLite (eine Tabelle pro Granularity)**: verworfen — schlechter fuer columnar scans, Overhead durch Connection-Pooling
- **HDF5**: verworfen — schlechteres Tooling-Oekosystem, h5py-Wartung fragwuerdig
- **CSV**: verworfen — keine Typen, kein schneller columnar read, File-Groesse 3-5x
- **DuckDB**: ernsthaft in Erwaegung gezogen fuer Phase 3+ (Backtest-Queries), aber P1 zu frueh

## References

- `src/quant_trader/data/cache.py`
- `src/quant_trader/core/types.py` (Granularity, Bar)
- NFR-Data-1 (Parquet-Cache, APPROVED)
- NFR-Rel-1 (idempotent, APPROVED)
- ADR 0004 (Cache-Strategie)
