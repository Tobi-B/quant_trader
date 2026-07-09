# QuantTrader - Architektur

> **Single Point of Truth fuer Modul-Verantwortlichkeiten und Datenflüsse.** Wird in Verbindung
> mit `AGENTS.md`, `docs/STATE.md` und den Slice-PRDs gelesen. Architektur-Entscheidungen leben
> in `docs/adr/`.

## 1. Layered Architecture

```
+---------------------------------------------------------------+
|  CLI Entry Points                                             |
|    quant_trader.cli  (qtrader Befehl, Phase 0)                |
|    quant_trader.universe  (load, list)                        |
|    quant_trader.data  (fetch single + universe)               |
|    quant_trader.strategies  (run, Phase 2.5 geplant)          |
+---------------------------------------------------------------+
                          |
                          v
+---------------------------------------------------------------+
|  Application Layer                                           |
|    data/service.py     Fetch + Cache orchestration           |
|    universe/loader.py  Preset -> Store                        |
|    strategies/runner   Signal-Generierung (Phase 2.5)        |
|    backtest/engine     Backtest (Phase 3)                     |
+---------------------------------------------------------------+
                          |
                          v
+---------------------------------------------------------------+
|  Domain Layer                                                |
|    core/types.py       Bar, Granularity, Preset               |
|    core/errors.py      DataError-Hierarchie                   |
|    strategies/types    Action, Signal, PortfolioState         |
|    strategies/base     StrategyBase, MultiTickerStrategyBase  |
+---------------------------------------------------------------+
                          |
                          v
+---------------------------------------------------------------+
|  Infrastructure Layer                                        |
|    data/provider.py    DataProvider Protocol                  |
|    data/fallback.py    FallbackProvider Decorator             |
|    data/cache.py       ParquetCache (pyarrow + pandas)        |
|    data/factory.py     ProviderChain-Assembly                |
|    strategies/loader   StrategyLoader + Registry             |
|    live/adapter        BrokerAdapter Protocol (Phase 5)       |
+---------------------------------------------------------------+
                          |
                          v
+---------------------------------------------------------------+
|  External                                                    |
|    AlphaVantage API, yfinance, StockData.org, IBKR TWS        |
+---------------------------------------------------------------+
```

**Layer-Regeln (Konvention):**
- Aufrufe gehen nur **abwaerts** (Application -> Domain -> Infrastructure -> External).
- Infrastructure darf Domain kennen, aber nicht umgekehrt.
- Domain kennt weder Application noch Infrastructure.
- CLI darf alle Layer kennen, ist aber selbst nur Entry-Point.

## 2. Module-Responsibilities

| Modul                            | Verantwortlich fuer                              | Kennt keine                         |
|----------------------------------|--------------------------------------------------|--------------------------------------|
| `core.config`                    | Settings, env-Loading, Paths                     | alles Konkrete                       |
| `core.logging`                   | structlog-Setup, Logger-Factory                  | alles Konkrete                       |
| `core.errors`                    | Fehler-Hierarchie                                | alles Konkrete                       |
| `core.types`                     | Geteilte Value-Objects (Bar, Granularity, Preset)| I/O                                  |
| `data.provider`                  | Vertrag fuer Marktdaten-Provider                 | Cache, Service                       |
| `data.alpha_vantage`             | AlphaVantage-spezifische HTTP-Calls              | Cache, andere Provider               |
| `data.yfinance_provider`         | YFinance-spezifische Calls                       | Cache, andere Provider               |
| `data.stockdata_provider`        | StockData.org-spezifische Calls                  | Cache, andere Provider               |
| `data.fallback`                  | Decorator fuer Provider-Kette                    | YAML, CLI                            |
| `data.cache`                     | Parquet-Lese/-Schreib-Cache                      | Provider                             |
| `data.factory`                   | ProviderChain-Assembly aus Settings              | CLI                                  |
| `data.service`                   | Cache-Check -> Provider -> Cache-Write           | CLI                                  |
| `universe.presets`               | YAML-Lesen von Presets                           | Store                                |
| `universe.store`                 | Persistenz von geladenen Universen               | CLI                                  |
| `universe.loader`                | Orchestriert Preset -> Store                     | YAML-Pfade                           |
| `strategies.types`               | Action, Signal, PortfolioState, StrategyConfig   | -                                     |
| `strategies.errors`              | StrategyError-Hierarchie                         | -                                     |
| `strategies.base`                | StrategyBase + MultiTickerStrategyBase ABCs      | Loader                               |
| `strategies.loader`              | Registry + YAML-Loader                           | konkrete Strategien                  |
| `strategies.sma_cross`           | SMA-Crossover Strategie (P2.2)                   | -                                     |
| `strategies.momentum`            | Momentum 12-1 Strategie (P2.2)                   | -                                     |
| `strategies.rsi_mean_reversion`  | RSI Strategie (P2.3)                             | -                                     |
| `strategies.etf_rotation`        | ETF Top-N Rotation Strategie (P2.4)              | -                                     |
| `backtest.engine`                | Backtest-Ausfuehrung (P3)                        | CLI                                  |
| `backtest.metrics`               | Sharpe, MDD, CAGR (P3)                           | -                                     |
| `risk.sizing`                    | Position-Sizing (P4)                             | -                                     |
| `live.adapter`                   | BrokerAdapter Protocol (P5)                      | ib_insync                             |
| `live.ib_insync_adapter`         | ib_insync-Implementation (P5)                    | -                                     |
| `storage.journal`                | SQLite-Trade-Journal (P5)                        | -                                     |

## 3. Datenfluss

### 3.1 Marktdaten-Fetch (Phase 1)

```
User: python -m quant_trader.data SPY --start 2024-01-01 --end 2024-06-30
  -> data/cli.py: arg-parse, Settings laden
  -> data/factory.py: build_chain(settings) -> FallbackProvider(AV, [YF, SD])
  -> data/service.py: DataService.get(SPY, start, end, daily)
       -> cache.covers(SPY, daily, start, end)?
            | ja  -> cache.read(...) -> list[Bar]
            | nein -> provider.fetch(SPY, start, end, daily)  [AV, dann YF, dann SD]
                 -> cache.write(SPY, daily, bars) -> Parquet-File
  -> CLI: log fetch.summary, exit 0
```

### 3.2 Signal-Generierung (Phase 2.5, geplant)

```
User: python -m quant_trader.strategies run --strategy sma_cross --ticker SPY ...
  -> strategies/cli.py: arg-parse, Settings laden
  -> strategies/loader.py: load("sma_cross")
       -> strategies.yaml lesen -> params
       -> registry["sma_cross"] = SmaCrossStrategy
       -> SmaCrossStrategy(params=...)
  -> data/cache.py: read(SPY, daily, start, end) -> list[Bar]
  -> loop fuer jeden Bar:
       strategy.on_bar(bar, portfolio_state) -> [Signal]
       collect signals
  -> SignalFormatter.format_signals(signals, limit=100) -> Tabelle
  -> CLI: print Tabelle, log signal_runner.summary, exit 0
```

### 3.3 Backtest (Phase 3, geplant)

```
bars (ParquetCache)
  -> DataService.get(ticker, start, end, granularity)
  -> bars chronologisch in den BacktestEngine
  -> Strategy.on_bar(bar, portfolio) -> [Signals]
  -> BacktestEngine.process(signal)
       -> Fill (Markt-/Limit-Order-Simulation)
       -> Portfolio-Update (cash, positions)
       -> Equity-Curve-Snapshot
  -> ReportGenerator
       -> Metriken (Sharpe, MDD, CAGR, Win-Rate)
       -> Plotly-Charts (Equity, Drawdown, Trade-Distribution)
       -> JSON-Export
```

### 3.4 Live-Trading (Phase 5, geplant)

```
Market-Data-Tick (ib_insync Event)
  -> LiveDataAdapter: bar (1-min oder 5-min aggregiert)
  -> Strategy.on_bar(bar, portfolio)
  -> Signal(BUY, ticker, qty)
  -> OrderManager.submit(signal)
       -> BrokerAdapter.submit_order(...)
       -> SQLite-Journal (Order, Fill, Timestamp)
  -> Heartbeat/Reconnect-Loop (NFR-Rel-2)
  -> Tageszusammenfassung (NFR-Obs-2)
```

## 4. Cross-Cutting Concerns

### 4.1 Configuration

- Einzige Quelle: `quant_trader.core.config.Settings` (pydantic-settings, `@lru_cache`).
- Geladen aus `.env` (gitignored) + Defaults aus `Settings`-Klasse.
- Felder: `data_dir`, `universe_presets_path`, `db_path`, `log_level`, `alphavantage_key`, `stockdata_api_token`, `strategies_config_path` (geplant P2).
- **Konvention**: keine hard-coded Paths in Modulen. Immer `settings.<field>` oder Funktion mit `settings`-Parameter.

### 4.2 Logging

- `structlog` (JSON in Produktion, ConsoleRenderer in Dev).
- Konfiguration in `quant_trader.core.logging.configure_logging(level)`.
- **Konvention**: `log = get_logger(__name__)` auf Modul-Ebene. Kein `print`. Log-Events als `snake_case.action` (z.B. `cache.hit`, `provider.fetch`, `signal_runner.summary`).

### 4.3 Error-Hierarchie

Pro Layer ein Basis-Error:

| Layer         | Basis-Error       | Beispiele                                                |
|---------------|-------------------|----------------------------------------------------------|
| Core          | (none)            | -                                                        |
| Data          | `DataError`       | `ProviderError`, `RateLimitedError`, `TickerNotFoundError`, `DataUnavailableError` |
| Universe      | `KeyError`/Custom | `PresetNotFoundError`                                    |
| Strategies    | `StrategyError`   | `StrategyConfigError`, `UnknownStrategyError`            |
| Backtest (P3) | `BacktestError`   | (geplant)                                                |
| Live (P5)     | `BrokerError`     | (geplant)                                                |

**Konvention**: Errors tragen die noetigen Felder als Attribute (`ticker`, `provider`, `reasons`), nicht nur in der Message. `str(exc)` ist die User-lesbare Form.

### 4.4 Type-Safety

- `mypy --strict` auf `src/` (siehe `pyproject.toml`).
- Public API = alles nicht mit `_` Prefix.
- Keine Wildcard-Imports.
- `Any` nur mit Begruendung im Commit-Body oder ADR.

## 5. Verweise

- `AGENTS.md` - Stack, Konventionen, Verification Gate
- `docs/STATE.md` - aktueller Projektstand, Resume-Punkt
- `docs/requirements/nfrs.md` - 13 NFRs mit IDs
- `docs/adr/` - 8 Architecture Decision Records
- `docs/prd/<phase>/<slice>.md` - Slice-PRDs
- `docs/uml/<phase>/<slice>.md` - Mermaid UML-Diagramme
- `docs/userstories/<phase>/<slice>.md` - User Stories
