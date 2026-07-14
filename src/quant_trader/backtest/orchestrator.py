"""BacktestOrchestrator: glue between strategy loader, cache, engine, and report builder.

The orchestrator is the single entry point the CLI uses to run a backtest.
It resolves a strategy name + ticker/universe to a loaded strategy instance,
reads the required bars from the Parquet cache, runs the
`BacktestEngine`, and (optionally) builds a report via `ReportBuilder`.
Validation errors are translated into the `BacktestError` hierarchy so
the CLI can present clean German messages to the user.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from quant_trader.backtest.engine import BacktestEngine
from quant_trader.backtest.errors import (
    CacheMissingError,
    InvalidParamsError,
    UnknownStrategyError,
)
from quant_trader.backtest.report.builder import ReportBuilder
from quant_trader.backtest.report.types import ReportPaths
from quant_trader.backtest.sizer import EqualWeightSizer
from quant_trader.backtest.types import BacktestConfig, BacktestResult, FillMode
from quant_trader.core.logging import get_logger
from quant_trader.core.types import Bar, Granularity
from quant_trader.data.cache import ParquetCache
from quant_trader.strategies.base import MultiTickerStrategyBase, StrategyBase
from quant_trader.strategies.loader import StrategyLoader
from quant_trader.universe.presets import PresetNotFoundError, PresetRepository

log = get_logger(__name__)


class BacktestOrchestrator:
    """Coordinates strategy loading, bar fetch, engine run, and optional report.

    Construction is dependency-injected: the orchestrator accepts a
    `ParquetCache` and a `StrategyLoader` so tests can pass in fakes. A
    default `ReportBuilder` is created on demand; callers can pass a
    pre-configured one to swap dependencies.
    """

    def __init__(
        self,
        cache: ParquetCache,
        loader: StrategyLoader,
        report_builder: ReportBuilder | None = None,
        reports_dir: Path = Path("./reports"),
    ) -> None:
        self._cache = cache
        self._loader = loader
        self._report_builder = report_builder or ReportBuilder()
        self._reports_dir = reports_dir

    @property
    def reports_dir(self) -> Path:
        return self._reports_dir

    def run(
        self,
        run_id: str,
        strategy_name: str,
        *,
        ticker: str = "",
        universe: str | None = None,
        start: date,
        end: date,
        granularity: Granularity = Granularity.DAILY,
        fill_mode: FillMode = FillMode.NEXT_OPEN,
        initial_cash: float = 100_000.0,
        write_report: bool = True,
    ) -> BacktestResult:
        if not run_id:
            raise InvalidParamsError("run_id darf nicht leer sein")
        if start > end:
            raise InvalidParamsError(
                f"start ({start.isoformat()}) liegt nach end ({end.isoformat()})"
            )
        if initial_cash <= 0:
            raise InvalidParamsError(f"initial_cash muss > 0 sein (got {initial_cash})")

        if not self._loader.is_registered(strategy_name):
            log.error(
                "backtest.unknown_strategy",
                strategy=strategy_name,
                available=self._loader.registered_names(),
            )
            raise UnknownStrategyError(strategy_name, self._loader.registered_names())

        log.info(
            "backtest.orchestrator.start",
            run_id=run_id,
            strategy=strategy_name,
            ticker=ticker,
            universe=universe,
            start=start.isoformat(),
            end=end.isoformat(),
            granularity=granularity.value,
            fill_mode=fill_mode.value,
            initial_cash=initial_cash,
        )

        try:
            strategy = self._loader.load(strategy_name, ticker=ticker)
        except FileNotFoundError as exc:
            raise InvalidParamsError(str(exc)) from exc

        if isinstance(strategy, StrategyBase):
            if not ticker:
                raise InvalidParamsError(
                    f"Strategy '{strategy_name}' ist Single-Ticker: --ticker ist erforderlich"
                )
            bars_by_ticker = self._read_single(strategy, ticker, granularity, start, end)
        elif isinstance(strategy, MultiTickerStrategyBase):
            tickers = self._resolve_multi_tickers(strategy, universe)
            bars_by_ticker = self._read_multi(tickers, granularity, start, end)
        else:
            raise InvalidParamsError(f"Unbekannter Strategy-Typ: {type(strategy).__name__}")

        config = BacktestConfig(
            initial_cash=initial_cash,
            fill_mode=fill_mode,
            sizer=EqualWeightSizer(),
            start=start,
            end=end,
        )
        engine = BacktestEngine(strategy, config)
        result = engine.run(bars_by_ticker)

        if write_report:
            paths: ReportPaths = self._report_builder.build(
                result, self._reports_dir, run_id=run_id
            )
            log.info(
                "backtest.orchestrator.report_written",
                run_id=run_id,
                html=str(paths.equity_html),
                json=str(paths.result_json),
            )

        log.info(
            "backtest.orchestrator.complete",
            run_id=run_id,
            strategy=result.strategy_name,
            final_equity=result.final_equity,
            trades=len(result.trades),
        )
        return result

    def _resolve_multi_tickers(
        self,
        strategy: MultiTickerStrategyBase,
        universe_arg: str | None,
    ) -> list[str]:
        if universe_arg:
            from quant_trader.core.config import get_settings

            repo = PresetRepository(get_settings().universe_presets_path)
            try:
                preset = repo.get(universe_arg)
            except PresetNotFoundError as exc:
                raise InvalidParamsError(
                    f"Universe-Preset '{universe_arg}' nicht gefunden: {exc.name}"
                ) from exc
            return [t.upper() for t in preset.tickers]
        params_universe = strategy.params.get("universe")
        if not params_universe:
            raise InvalidParamsError(
                "Multi-Ticker-Strategie benoetigt 'universe' in den Parametern "
                "oder '--universe PRESET'"
            )
        return [str(t).upper() for t in params_universe]

    def _read_single(
        self,
        strategy: StrategyBase,
        ticker: str,
        granularity: Granularity,
        start: date,
        end: date,
    ) -> dict[str, list[Bar]]:
        if not self._cache.exists(ticker, granularity):
            path = self._cache.path_for(ticker, granularity)
            log.error("backtest.cache_missing", ticker=ticker, path=str(path))
            raise CacheMissingError(ticker, path)
        return {ticker: self._cache.read(ticker, granularity, start, end)}

    def _read_multi(
        self,
        tickers: list[str],
        granularity: Granularity,
        start: date,
        end: date,
    ) -> dict[str, list[Bar]]:
        per_ticker: dict[str, list[Bar]] = {}
        for t in tickers:
            if not self._cache.exists(t, granularity):
                path = self._cache.path_for(t, granularity)
                log.error("backtest.cache_missing", ticker=t, path=str(path))
                raise CacheMissingError(t, path)
            per_ticker[t] = self._cache.read(t, granularity, start, end)
        return per_ticker


__all__ = ["BacktestOrchestrator"]
