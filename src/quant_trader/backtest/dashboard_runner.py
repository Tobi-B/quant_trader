"""DashboardRunner: UI-facing glue between the dashboard and the backtest orchestrator.

The dashboard is interactive, so it needs a thin shim that:
- validates the strategy name against the registered loader
- resolves a universe preset (if selected) to a ticker list
- generates a `run_id` for the dashboard-triggered run
- forwards the call to the existing `BacktestOrchestrator` with hard-coded
  defaults (`FillMode.NEXT_OPEN`, `Granularity.DAILY`, `initial_cash=100_000.0`)
- emits structured events `backtest.dashboard.start` / `backtest.dashboard.complete`
- re-raises `CacheMissingError` so the Streamlit layer can show a clean
  German message instead of crashing.

The runner is pure library code: it does not import Streamlit, which
keeps the unit tests fast and side-effect free.
"""

from __future__ import annotations

from datetime import date, datetime

from quant_trader.backtest.errors import (
    InvalidParamsError,
    UnknownStrategyError,
)
from quant_trader.backtest.orchestrator import BacktestOrchestrator
from quant_trader.backtest.types import BacktestResult, FillMode
from quant_trader.core.logging import get_logger
from quant_trader.core.types import Granularity
from quant_trader.strategies.loader import StrategyLoader
from quant_trader.universe.presets import PresetNotFoundError, PresetRepository

log = get_logger(__name__)


class DashboardRunner:
    """UI-facing helper that wires a dashboard request into the orchestrator.

    Construction is dependency-injected: a `BacktestOrchestrator`,
    `StrategyLoader` and `PresetRepository` are passed in. This keeps the
    runner testable without Streamlit and without touching global state.
    """

    def __init__(
        self,
        orchestrator: BacktestOrchestrator,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        self._orchestrator = orchestrator
        self._loader = loader
        self._presets = presets

    def run_request(
        self,
        strategy_name: str,
        ticker: str,
        universe_preset: str | None,
        start: date,
        end: date,
    ) -> tuple[str, BacktestResult]:
        if not self._loader.is_registered(strategy_name):
            log.error(
                "backtest.dashboard.unknown_strategy",
                strategy=strategy_name,
                available=self._loader.registered_names(),
            )
            raise UnknownStrategyError(strategy_name, self._loader.registered_names())

        resolved_ticker, resolved_universe = self._resolve_ticker(
            ticker=ticker, universe_preset=universe_preset
        )

        run_id = self._generate_run_id()

        log.info(
            "backtest.dashboard.start",
            run_id=run_id,
            strategy=strategy_name,
            ticker=resolved_ticker,
            universe=resolved_universe,
            start=start.isoformat(),
            end=end.isoformat(),
        )

        result = self._orchestrator.run(
            run_id,
            strategy_name=strategy_name,
            ticker=resolved_ticker,
            universe=resolved_universe,
            start=start,
            end=end,
            granularity=Granularity.DAILY,
            fill_mode=FillMode.NEXT_OPEN,
            initial_cash=100_000.0,
            write_report=True,
        )

        log.info(
            "backtest.dashboard.complete",
            run_id=run_id,
            strategy=result.strategy_name,
            final_equity=result.final_equity,
            trades=len(result.trades),
        )
        return run_id, result

    def _resolve_ticker(
        self,
        ticker: str,
        universe_preset: str | None,
    ) -> tuple[str, str | None]:
        if universe_preset:
            try:
                preset = self._presets.get(universe_preset)
            except PresetNotFoundError as exc:
                raise InvalidParamsError(f"Universe-Preset '{exc.name}' nicht gefunden") from exc
            tickers = [t.upper() for t in preset.tickers]
            if not tickers:
                raise InvalidParamsError(
                    f"Universe-Preset '{universe_preset}' enthaelt keine Ticker"
                )
            return "", universe_preset

        cleaned = ticker.strip().upper()
        if not cleaned:
            raise InvalidParamsError("Ticker oder Universe-Preset erforderlich")
        return cleaned, None

    @staticmethod
    def _generate_run_id() -> str:
        return datetime.now().strftime("%Y%m%dT%H%M%S")


__all__ = ["DashboardRunner"]
