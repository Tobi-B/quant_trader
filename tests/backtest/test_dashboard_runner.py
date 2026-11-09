"""Tests for the DashboardRunner (slice 3.5).

These tests focus on the runner contract:
- delegates to the orchestrator with the expected defaults
- validates the strategy against the loader registry
- resolves universe presets and normalises tickers
- re-raises `CacheMissingError` from the orchestrator
- emits structured `backtest.dashboard.start` / `backtest.dashboard.complete` events

The orchestrator is mocked at the boundary so we can assert on call
arguments without going through the full backtest pipeline.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest
import structlog

from quant_trader.backtest.dashboard_runner import DashboardRunner
from quant_trader.backtest.errors import (
    CacheMissingError,
    InvalidParamsError,
    UnknownStrategyError,
)
from quant_trader.backtest.types import BacktestResult, FillMode
from quant_trader.core.types import Bar, Granularity
from quant_trader.strategies import SmaCrossStrategy
from quant_trader.strategies.base import MultiTickerStrategyBase
from quant_trader.strategies.loader import StrategyLoader
from quant_trader.strategies.types import PortfolioState, Signal
from quant_trader.universe.presets import PresetRepository

_RUN_ID_PATTERN = re.compile(r"^\d{8}T\d{6}$")


class _SampleMultiTicker(MultiTickerStrategyBase):
    name: ClassVar[str] = "sample_multi"
    default_params: ClassVar[dict[str, Any]] = {"universe": ["SPY", "AGG"]}

    def warmup_bars(self) -> int:
        return 0

    def on_universe_bars(
        self,
        timestamp: datetime,
        bars_by_ticker: dict[str, Bar],
        portfolio: PortfolioState,
    ) -> list[Signal]:
        return []


@pytest.fixture
def strategies_yaml(tmp_path: Path) -> Path:
    cfg = tmp_path / "strategies.yaml"
    cfg.write_text(
        "sma_cross:\n  params: {fast: 5, slow: 10}\nsample_multi:\n  params: {}\n",
        encoding="utf-8",
    )
    return cfg


@pytest.fixture
def loader(strategies_yaml: Path) -> StrategyLoader:
    ldr = StrategyLoader(strategies_yaml)
    ldr.register(SmaCrossStrategy)
    ldr.register(_SampleMultiTicker)
    return ldr


@pytest.fixture
def presets_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "presets.yaml"
    p.write_text(
        "etfs:\n  description: 'ETFs'\n  tickers: [spy, agg]\n"
        "empty:\n  description: 'empty'\n  tickers: []\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def presets(presets_yaml: Path) -> PresetRepository:
    return PresetRepository(presets_yaml)


def _fake_result() -> BacktestResult:
    return BacktestResult(
        strategy_name="sma_cross",
        params={},
        start=date(2024, 1, 2),
        end=date(2024, 3, 31),
        fill_mode=FillMode.NEXT_OPEN,
        initial_cash=100_000.0,
        final_equity=101_000.0,
        trades=[],
        equity_curve=[],
    )


class TestDashboardRunnerHappyPath:
    def test_run_request_delegates_to_orchestrator_with_defaults(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        orchestrator.run.return_value = _fake_result()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        returned_run_id, result = runner.run_request(
            strategy_name="sma_cross",
            ticker="spy",
            universe_preset=None,
            start=date(2024, 1, 2),
            end=date(2024, 3, 31),
        )

        assert result is orchestrator.run.return_value
        orchestrator.run.assert_called_once()
        call = orchestrator.run.call_args
        run_id = call.args[0]
        kwargs = call.kwargs
        assert _RUN_ID_PATTERN.match(run_id)
        assert _RUN_ID_PATTERN.match(returned_run_id)
        assert run_id == returned_run_id
        assert kwargs["strategy_name"] == "sma_cross"
        assert kwargs["ticker"] == "SPY"
        assert kwargs["universe"] is None
        assert kwargs["start"] == date(2024, 1, 2)
        assert kwargs["end"] == date(2024, 3, 31)
        assert kwargs["granularity"] == Granularity.DAILY
        assert kwargs["fill_mode"] == FillMode.NEXT_OPEN
        assert kwargs["initial_cash"] == 100_000.0
        assert kwargs["write_report"] is True

    def test_run_request_returns_orchestrator_result(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        orchestrator.run.return_value = _fake_result()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        _, result = runner.run_request(
            strategy_name="sma_cross",
            ticker="SPY",
            universe_preset=None,
            start=date(2024, 1, 2),
            end=date(2024, 3, 31),
        )

        assert result.strategy_name == "sma_cross"
        assert result.final_equity == 101_000.0


class TestDashboardRunnerValidation:
    def test_unknown_strategy_raises_with_available_list(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        with pytest.raises(UnknownStrategyError) as exc_info:
            runner.run_request(
                strategy_name="does_not_exist",
                ticker="SPY",
                universe_preset=None,
                start=date(2024, 1, 2),
                end=date(2024, 3, 31),
            )

        assert exc_info.value.name == "does_not_exist"
        assert "sma_cross" in exc_info.value.available
        orchestrator.run.assert_not_called()

    def test_empty_ticker_and_no_universe_raises_invalid_params(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        with pytest.raises(InvalidParamsError, match="Ticker oder Universe-Preset"):
            runner.run_request(
                strategy_name="sma_cross",
                ticker="   ",
                universe_preset=None,
                start=date(2024, 1, 2),
                end=date(2024, 3, 31),
            )

        orchestrator.run.assert_not_called()

    def test_unknown_universe_preset_raises_invalid_params(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        with pytest.raises(InvalidParamsError, match="Universe 'does_not_exist' nicht gefunden"):
            runner.run_request(
                strategy_name="sma_cross",
                ticker="",
                universe_preset="does_not_exist",
                start=date(2024, 1, 2),
                end=date(2024, 3, 31),
            )

        orchestrator.run.assert_not_called()

    def test_dynamic_universe_fallback_when_no_preset_matches(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
        tmp_path: Path,
    ) -> None:
        from datetime import datetime

        from quant_trader.universe.dynamic_store import DynamicUniverse, DynamicUniverseStore

        dynamic_store = DynamicUniverseStore(tmp_path / "dynamic")
        dynamic_store.save(
            DynamicUniverse(
                name="my_dynamic",
                built_from_snapshot="snap-1",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                filter_description="",
                filters={},
                tickers=("spy", "qqq"),
            )
        )
        orchestrator = MagicMock()
        orchestrator.run.return_value = _fake_result()
        runner = DashboardRunner(
            orchestrator=orchestrator, loader=loader, presets=presets, dynamic_store=dynamic_store
        )

        runner.run_request(
            strategy_name="sma_cross",
            ticker="",
            universe_preset="my_dynamic",
            start=date(2024, 1, 2),
            end=date(2024, 3, 31),
        )

        _, kwargs = orchestrator.run.call_args
        assert kwargs["universe"] == "my_dynamic"

    def test_dynamic_universe_not_found_anywhere_raises_invalid_params(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
        tmp_path: Path,
    ) -> None:
        from quant_trader.universe.dynamic_store import DynamicUniverseStore

        dynamic_store = DynamicUniverseStore(tmp_path / "dynamic")
        orchestrator = MagicMock()
        runner = DashboardRunner(
            orchestrator=orchestrator, loader=loader, presets=presets, dynamic_store=dynamic_store
        )

        with pytest.raises(InvalidParamsError, match="Universe 'nowhere' nicht gefunden"):
            runner.run_request(
                strategy_name="sma_cross",
                ticker="",
                universe_preset="nowhere",
                start=date(2024, 1, 2),
                end=date(2024, 3, 31),
            )

    def test_empty_universe_preset_raises_invalid_params(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        with pytest.raises(InvalidParamsError, match="keine Ticker"):
            runner.run_request(
                strategy_name="sma_cross",
                ticker="",
                universe_preset="empty",
                start=date(2024, 1, 2),
                end=date(2024, 3, 31),
            )

        orchestrator.run.assert_not_called()


class TestDashboardRunnerResolution:
    def test_universe_preset_resolves_to_uppercase_tickers(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        orchestrator.run.return_value = _fake_result()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        runner.run_request(
            strategy_name="sma_cross",
            ticker="ignored_when_universe_set",
            universe_preset="etfs",
            start=date(2024, 1, 2),
            end=date(2024, 3, 31),
        )

        kwargs = orchestrator.run.call_args.kwargs
        assert kwargs["universe"] == "etfs"
        assert kwargs["ticker"] == ""

    def test_custom_ticker_is_uppercased_and_stripped(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        orchestrator.run.return_value = _fake_result()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        runner.run_request(
            strategy_name="sma_cross",
            ticker="  aapl  ",
            universe_preset=None,
            start=date(2024, 1, 2),
            end=date(2024, 3, 31),
        )

        kwargs = orchestrator.run.call_args.kwargs
        assert kwargs["ticker"] == "AAPL"
        assert kwargs["universe"] is None

    def test_run_id_format_is_yyyymmddthhmmss(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        orchestrator.run.return_value = _fake_result()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        runner.run_request(
            strategy_name="sma_cross",
            ticker="SPY",
            universe_preset=None,
            start=date(2024, 1, 2),
            end=date(2024, 3, 31),
        )

        run_id = orchestrator.run.call_args.args[0]
        assert _RUN_ID_PATTERN.match(run_id), f"unexpected run_id format: {run_id}"


class TestDashboardRunnerMultiTicker:
    """A multi-ticker strategy never reads the Ticker field (the strategy is
    instantiated without it - see StrategyLoader.load), so an empty ticker
    and no universe_preset must not be treated as 'nothing selected'."""

    def test_no_override_and_empty_ticker_does_not_raise(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        orchestrator.run.return_value = _fake_result()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        runner.run_request(
            strategy_name="sample_multi",
            ticker="",
            universe_preset=None,
            start=date(2024, 1, 2),
            end=date(2024, 3, 31),
        )

        kwargs = orchestrator.run.call_args.kwargs
        assert kwargs["universe"] is None
        assert kwargs["ticker"] == ""

    def test_typed_ticker_is_ignored_not_forwarded(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        """Even if a ticker were typed, it must not reach the orchestrator as
        `ticker=` for a multi-ticker strategy - it would be silently dropped
        by StrategyLoader.load anyway, so forwarding it would be misleading."""
        orchestrator = MagicMock()
        orchestrator.run.return_value = _fake_result()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        runner.run_request(
            strategy_name="sample_multi",
            ticker="AAPL",
            universe_preset=None,
            start=date(2024, 1, 2),
            end=date(2024, 3, 31),
        )

        kwargs = orchestrator.run.call_args.kwargs
        assert kwargs["ticker"] == ""

    def test_universe_preset_still_resolves_for_multi_ticker(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        orchestrator.run.return_value = _fake_result()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        runner.run_request(
            strategy_name="sample_multi",
            ticker="",
            universe_preset="etfs",
            start=date(2024, 1, 2),
            end=date(2024, 3, 31),
        )

        kwargs = orchestrator.run.call_args.kwargs
        assert kwargs["universe"] == "etfs"


class TestDashboardRunnerErrorPropagation:
    def test_cache_missing_is_re_raised(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
        tmp_path: Path,
    ) -> None:
        orchestrator = MagicMock()
        orchestrator.run.side_effect = CacheMissingError(
            "ZZZZ", tmp_path / "cache" / "ZZZZ.parquet"
        )
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        with pytest.raises(CacheMissingError) as exc_info:
            runner.run_request(
                strategy_name="sma_cross",
                ticker="ZZZZ",
                universe_preset=None,
                start=date(2024, 1, 2),
                end=date(2024, 3, 31),
            )
        assert exc_info.value.ticker == "ZZZZ"


class TestDashboardRunnerLogging:
    def test_emits_start_and_complete_events(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        orchestrator.run.return_value = _fake_result()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        with structlog.testing.capture_logs() as captured:
            runner.run_request(
                strategy_name="sma_cross",
                ticker="spy",
                universe_preset=None,
                start=date(2024, 1, 2),
                end=date(2024, 3, 31),
            )

        events = [entry["event"] for entry in captured]
        assert "backtest.dashboard.start" in events
        assert "backtest.dashboard.complete" in events

        start_entry = next(e for e in captured if e["event"] == "backtest.dashboard.start")
        assert start_entry["strategy"] == "sma_cross"
        assert start_entry["ticker"] == "SPY"
        assert start_entry["universe"] is None
        assert start_entry["start"] == "2024-01-02"
        assert start_entry["end"] == "2024-03-31"
        assert _RUN_ID_PATTERN.match(start_entry["run_id"])

        complete_entry = next(e for e in captured if e["event"] == "backtest.dashboard.complete")
        assert complete_entry["strategy"] == "sma_cross"
        assert complete_entry["final_equity"] == 101_000.0
        assert complete_entry["trades"] == 0

    def test_emits_unknown_strategy_event(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
    ) -> None:
        orchestrator = MagicMock()
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        with (
            structlog.testing.capture_logs() as captured,
            pytest.raises(UnknownStrategyError),
        ):
            runner.run_request(
                strategy_name="ghost",
                ticker="SPY",
                universe_preset=None,
                start=date(2024, 1, 2),
                end=date(2024, 3, 31),
            )

        events = [entry["event"] for entry in captured]
        assert "backtest.dashboard.unknown_strategy" in events
        unknown = next(e for e in captured if e["event"] == "backtest.dashboard.unknown_strategy")
        assert unknown["strategy"] == "ghost"
        assert "sma_cross" in unknown["available"]

    def test_does_not_emit_complete_when_orchestrator_raises(
        self,
        loader: StrategyLoader,
        presets: PresetRepository,
        tmp_path: Path,
    ) -> None:
        orchestrator = MagicMock()
        orchestrator.run.side_effect = CacheMissingError("ZZZZ", tmp_path / "cache.parquet")
        runner = DashboardRunner(orchestrator=orchestrator, loader=loader, presets=presets)

        with structlog.testing.capture_logs() as captured, pytest.raises(CacheMissingError):
            runner.run_request(
                strategy_name="sma_cross",
                ticker="ZZZZ",
                universe_preset=None,
                start=date(2024, 1, 2),
                end=date(2024, 3, 31),
            )

        events = [entry["event"] for entry in captured]
        assert "backtest.dashboard.start" in events
        assert "backtest.dashboard.complete" not in events
