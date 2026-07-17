# UML: Slice 2.7 - Long Capital / Short Labor

Status:    APPROVED
Phase:     P2 Strategien
Slice:     2.7 Long Capital / Short Labor Strategie
Story:     US-P2.9 Long Capital / Short Labor als monatliches Pair

Mapped Requirements:
- NFR-Data-1: Cache-Pfad bleibt unveraendert
- NFR-Obs-1: Strukturiertes Logging der Spread-Berechnung
- NFR-Strategy-1: Determinismus (keine Randomness)

Die Strategie ist eine reine Erweiterung des bestehenden
Multi-Ticker-Frameworks. Sie veraendert weder die Registry noch
den Runner. Sie liest Bars aus dem bestehenden Parquet-Cache.

## Structure

```mermaid
classDiagram
    class MultiTickerStrategyBase {
        <<abstract>>
        +name: str
        +version: str
        +default_params: dict
        +warmup_bars() int
        +on_universe_bars(timestamp, bars_by_ticker, portfolio) list~Signal~
    }
    class LongCapitalShortLaborStrategy {
        +name = "long_capital_short_labor"
        +version = "1.0.0"
        +default_params: dict
        -_long_universe: list~str~
        -_short_universe: list~str~
        -_long_weight: float
        -_short_weight: float
        -_entry_threshold: float
        -_exit_threshold: float
        -_lookback_bars: int
        -_history: dict~str,deque~Bar~~
        -_in_position: bool
        +warmup_bars() int
        +on_universe_bars(timestamp, bars_by_ticker, portfolio) list~Signal~
        -_append_history(bars_by_ticker) None
        -_all_warm(bars_by_ticker) bool
        -_compute_basket_return(universe, bars_by_ticker) float
        -_emit_entry_signals(timestamp) list~Signal~
        -_emit_exit_signals(timestamp) list~Signal~
    }
    class Signal {
        +timestamp: datetime
        +ticker: str
        +action: Action
        +reason: str
    }
    class Action {
        <<enumeration>>
        BUY
        SELL
    }
    class Bar {
        +timestamp: datetime
        +open: float
        +high: float
        +low: float
        +close: float
        +volume: int
    }

    LongCapitalShortLaborStrategy --|> MultiTickerStrategyBase
    LongCapitalShortLaborStrategy ..> Signal
    Signal ..> Action
    LongCapitalShortLaborStrategy --> Bar
```

## Flow

```mermaid
flowchart TD
    A([Runner ruft on_universe_bars mit timestamp und bars_by_ticker auf]) --> B[History pro Ticker fortschreiben]
    B --> C{Rebalance-Tag?}
    C -->|Nein| D[Leere Signal-Liste zurueckgeben]
    C -->|Ja| E{Alle Korb-Ticker warm?}
    E -->|Nein| F[Warmup-Log und leere Liste zurueckgeben]
    E -->|Ja| G[Basket-Returns berechnen long_avg und short_avg]
    G --> H[Spread = long_avg - short_avg]
    H --> I{spread > entry_threshold?}
    I -->|Ja| J{In Position?}
    I -->|Nein| K{spread < exit_threshold?}
    J -->|Nein| L[Entry-Signale emittieren BUY Long + SELL Short]
    J -->|Ja| M[Hold keine neuen Signale]
    K -->|Ja| N{In Position?}
    K -->|Nein| M
    N -->|Ja| O[Exit-Signale emittieren SELL Long + BUY Short]
    N -->|Nein| M
    L --> P[Log rebalance mit Spread und Returns]
    O --> P
    M --> P
    P --> Q([Signal-Liste zurueckgeben])
    D --> Q
    F --> Q
```

## Sequence

```mermaid
sequenceDiagram
    actor R as SignalRunner
    participant S as LongCapitalShortLaborStrategy
    participant H as History pro Ticker
    participant C as ParquetCache
    participant P as PortfolioState

    R->>C: read_bars(long_universe + short_universe)
    C-->>R: list[Bar] pro Ticker
    R->>S: on_universe_bars(timestamp, bars_by_ticker, portfolio)
    S->>H: append history pro Ticker
    alt Rebalance-Tag und alle warm
        S->>S: compute long_avg return ueber 6 Monate
        S->>S: compute short_avg return ueber 6 Monate
        S->>S: spread = long_avg - short_avg
        alt spread > +2% und nicht investiert
            S->>R: BUY fuer jeden Long-Ticker
            S->>R: SELL fuer jeden Short-Ticker
        else spread < 0% und investiert
            S->>R: SELL fuer jeden Long-Ticker
            S->>R: BUY fuer jeden Short-Ticker
        else
            S->>R: leere Liste Hold
        end
        S->>R: log rebalance mit Spread und Basket-Returns
    else Kein Rebalance-Tag oder Warmup aktiv
        S->>R: leere Liste
    end
    R-->>P: Signale angewendet
```
