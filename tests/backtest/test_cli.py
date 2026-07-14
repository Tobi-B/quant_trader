"""Tests for the Backtest CLI: parser, orchestrator wiring, exit codes, list output."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

import pytest

from quant_trader.core.types import Bar, Granularity
from quant_trader.data.cache import ParquetCache
from quant_trader.strategies import EtfRotationStrategy, SmaCrossStrategy
from quant_trader.strategies.base import MultiTickerStrategyBase
from quant_trader.strategies.loader import StrategyLoader
from quant_trader.strategies.types import PortfolioState, Signal


def _bar(close: float, day: int, ticker: str = "SPY") -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, 2, 16, 0) + timedelta(days=day),
        open=close - 1.0,
        high=close + 1.0,
        low=close - 1.5,
        close=close,
        adjusted_close=close,
        volume=1000,
    )


def _trend_bars(n: int = 60) -> list[Bar]:
    closes: list[float] = []
    for i in range(n):
        base = 100.0 - i * 1.5 if i < 25 else 100.0 - 25 * 1.5 + (i - 25) * 3.0
        closes.append(base)
    return [_bar(close=c, day=i) for i, c in enumerate(closes)]


def _write_cache(cache: ParquetCache, ticker: str, bars: list[Bar]) -> None:
    cache.write(ticker, Granularity.DAILY, bars)


class _NoUniverseMultiStrategy(MultiTickerStrategyBase):
    """Multi-ticker strategy without a default universe for negative tests."""

    name: ClassVar[str] = "no_universe_multi"
    version: ClassVar[str] = "1.0.0"
    default_params: ClassVar[dict[str, Any]] = {}

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
        "sma_cross:\n  params: {fast: 5, slow: 10}\n"
        "etf_rotation:\n  params:\n    universe: [SPY, AGG]\n    top_n: 1\n    "
        "lookback_months: 1\n    rebalance_freq: monthly\n"
        "no_universe_multi:\n  params: {}\n",
        encoding="utf-8",
    )
    return cfg


@pytest.fixture
def presets_yaml(tmp_path: Path) -> Path:
    presets = tmp_path / "universe_presets.yaml"
    presets.write_text("alt:\n  description: x\n  tickers: [TLT, IEF]\n", encoding="utf-8")
    return presets


@pytest.fixture
def loader(strategies_yaml: Path) -> StrategyLoader:
    ldr = StrategyLoader(strategies_yaml)
    ldr.register(SmaCrossStrategy)
    ldr.register(EtfRotationStrategy)
    ldr.register(_NoUniverseMultiStrategy)
    return ldr


class TestCLIParser:
    def test_parser_requires_command(self) -> None:
        from quant_trader.backtest.cli import build_parser

        with pytest.raises(SystemExit):
            build_parser().parse_args([])

    def test_run_requires_strategy_start_end(self) -> None:
        from quant_trader.backtest.cli import build_parser

        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["run"])

    def test_run_minimal_args(self) -> None:
        from quant_trader.backtest.cli import build_parser

        ns = build_parser().parse_args(
            [
                "run",
                "--strategy",
                "sma_cross",
                "--ticker",
                "SPY",
                "--start",
                "2024-01-02",
                "--end",
                "2024-03-31",
            ]
        )
        assert ns.command == "run"
        assert ns.strategy == "sma_cross"
        assert ns.ticker == "SPY"
        assert ns.start == "2024-01-02"
        assert ns.end == "2024-03-31"
        assert ns.granularity == "daily"
        assert ns.fill_mode == "next_open"
        assert ns.initial_cash == 100_000.0
        assert ns.no_report is False

    def test_run_fill_mode_choices(self) -> None:
        from quant_trader.backtest.cli import build_parser

        with pytest.raises(SystemExit):
            build_parser().parse_args(
                [
                    "run",
                    "--strategy",
                    "sma_cross",
                    "--ticker",
                    "SPY",
                    "--start",
                    "2024-01-02",
                    "--end",
                    "2024-03-31",
                    "--fill-mode",
                    "bogus",
                ]
            )

    def test_run_granularity_choices(self) -> None:
        from quant_trader.backtest.cli import build_parser

        with pytest.raises(SystemExit):
            build_parser().parse_args(
                [
                    "run",
                    "--strategy",
                    "sma_cross",
                    "--ticker",
                    "SPY",
                    "--start",
                    "2024-01-02",
                    "--end",
                    "2024-03-31",
                    "--granularity",
                    "weekly",
                ]
            )

    def test_run_no_report_flag(self) -> None:
        from quant_trader.backtest.cli import build_parser

        ns = build_parser().parse_args(
            [
                "run",
                "--strategy",
                "sma_cross",
                "--ticker",
                "SPY",
                "--start",
                "2024-01-02",
                "--end",
                "2024-03-31",
                "--no-report",
            ]
        )
        assert ns.no_report is True

    def test_run_initial_cash_float(self) -> None:
        from quant_trader.backtest.cli import build_parser

        ns = build_parser().parse_args(
            [
                "run",
                "--strategy",
                "sma_cross",
                "--ticker",
                "SPY",
                "--start",
                "2024-01-02",
                "--end",
                "2024-03-31",
                "--initial-cash",
                "50000",
            ]
        )
        assert ns.initial_cash == 50000.0

    def test_list_command(self) -> None:
        from quant_trader.backtest.cli import build_parser

        ns = build_parser().parse_args(["list"])
        assert ns.command == "list"


class TestCLIMainRun:
    def _setup(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
    ) -> None:
        monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("STRATEGIES_CONFIG_PATH", str(strategies_yaml))
        monkeypatch.setenv("UNIVERSE_PRESETS_PATH", str(tmp_path / "presets.yaml"))
        (tmp_path / "presets.yaml").write_text("alt:\n  description: x\n  tickers: [TLT, IEF]\n")
        monkeypatch.setattr("quant_trader.backtest.cli.configure_logging", lambda *a, **kw: None)
        from quant_trader.core.config import get_settings

        get_settings.cache_clear()

    def test_run_happy_path_writes_report_and_prints_console(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._setup(monkeypatch, tmp_path, strategies_yaml)
        data_dir = tmp_path / "data"
        _write_cache(ParquetCache(data_dir), "SPY", _trend_bars(60))
        reports_dir = tmp_path / "reports"

        from quant_trader.backtest.cli import main

        rc = main(
            [
                "run",
                "--strategy",
                "sma_cross",
                "--ticker",
                "SPY",
                "--start",
                "2024-01-02",
                "--end",
                "2024-03-31",
                "--reports-dir",
                str(reports_dir),
            ]
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert "Backtest:" in out
        assert "Total Return" in out
        runs = list(reports_dir.iterdir())
        assert len(runs) == 1
        assert (runs[0] / "equity_curve.html").exists()
        assert (runs[0] / "result.json").exists()

    def test_run_no_report_skips_files(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._setup(monkeypatch, tmp_path, strategies_yaml)
        data_dir = tmp_path / "data"
        _write_cache(ParquetCache(data_dir), "SPY", _trend_bars(60))
        reports_dir = tmp_path / "reports"

        from quant_trader.backtest.cli import main

        rc = main(
            [
                "run",
                "--strategy",
                "sma_cross",
                "--ticker",
                "SPY",
                "--start",
                "2024-01-02",
                "--end",
                "2024-03-31",
                "--no-report",
                "--reports-dir",
                str(reports_dir),
            ]
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert "Total Return" in out
        assert not reports_dir.exists() or list(reports_dir.iterdir()) == []

    def test_run_with_same_close_fill_mode(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._setup(monkeypatch, tmp_path, strategies_yaml)
        data_dir = tmp_path / "data"
        _write_cache(ParquetCache(data_dir), "SPY", _trend_bars(60))
        reports_dir = tmp_path / "reports"

        from quant_trader.backtest.cli import main

        rc = main(
            [
                "run",
                "--strategy",
                "sma_cross",
                "--ticker",
                "SPY",
                "--start",
                "2024-01-02",
                "--end",
                "2024-03-31",
                "--fill-mode",
                "same_close",
                "--no-report",
                "--reports-dir",
                str(reports_dir),
            ]
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert "same_close" in out

    def test_run_with_custom_initial_cash(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._setup(monkeypatch, tmp_path, strategies_yaml)
        data_dir = tmp_path / "data"
        _write_cache(ParquetCache(data_dir), "SPY", _trend_bars(60))
        reports_dir = tmp_path / "reports"

        from quant_trader.backtest.cli import main

        rc = main(
            [
                "run",
                "--strategy",
                "sma_cross",
                "--ticker",
                "SPY",
                "--start",
                "2024-01-02",
                "--end",
                "2024-03-31",
                "--initial-cash",
                "50000",
                "--no-report",
                "--reports-dir",
                str(reports_dir),
            ]
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert "50,000.00" in out

    def test_run_unknown_strategy_returns_1(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._setup(monkeypatch, tmp_path, strategies_yaml)
        from quant_trader.backtest.cli import main

        rc = main(
            [
                "run",
                "--strategy",
                "does_not_exist",
                "--ticker",
                "SPY",
                "--start",
                "2024-01-02",
                "--end",
                "2024-03-31",
            ]
        )
        out = capsys.readouterr()
        assert rc == 1
        assert "unbekannte Strategie" in out.err
        assert "does_not_exist" in out.err
        assert "sma_cross" in out.err

    def test_run_missing_cache_returns_1(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._setup(monkeypatch, tmp_path, strategies_yaml)
        from quant_trader.backtest.cli import main

        rc = main(
            [
                "run",
                "--strategy",
                "sma_cross",
                "--ticker",
                "ZZZZ",
                "--start",
                "2024-01-02",
                "--end",
                "2024-01-31",
            ]
        )
        out = capsys.readouterr()
        assert rc == 1
        assert "Kein Cache" in out.err
        assert "ZZZZ" in out.err
        assert "python -m quant_trader.data" in out.err

    def test_run_single_ticker_without_ticker_returns_1(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._setup(monkeypatch, tmp_path, strategies_yaml)
        from quant_trader.backtest.cli import main

        rc = main(
            [
                "run",
                "--strategy",
                "sma_cross",
                "--start",
                "2024-01-02",
                "--end",
                "2024-03-31",
            ]
        )
        out = capsys.readouterr()
        assert rc == 1
        assert "--ticker ist erforderlich" in out.err

    def test_run_multi_ticker_without_universe_returns_1(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._setup(monkeypatch, tmp_path, strategies_yaml)
        from quant_trader.backtest.cli import main

        rc = main(
            [
                "run",
                "--strategy",
                "no_universe_multi",
                "--start",
                "2024-01-02",
                "--end",
                "2024-03-31",
            ]
        )
        out = capsys.readouterr()
        assert rc == 1
        assert "universe" in out.err.lower()

    def test_run_invalid_date_returns_1(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._setup(monkeypatch, tmp_path, strategies_yaml)
        from quant_trader.backtest.cli import main

        rc = main(
            [
                "run",
                "--strategy",
                "sma_cross",
                "--ticker",
                "SPY",
                "--start",
                "not-a-date",
                "--end",
                "2024-03-31",
            ]
        )
        out = capsys.readouterr()
        assert rc == 1
        assert "Datum" in out.err

    def test_run_multi_ticker_with_preset(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        presets_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("STRATEGIES_CONFIG_PATH", str(strategies_yaml))
        monkeypatch.setenv("UNIVERSE_PRESETS_PATH", str(presets_yaml))
        monkeypatch.setattr("quant_trader.backtest.cli.configure_logging", lambda *a, **kw: None)
        from quant_trader.core.config import get_settings

        get_settings.cache_clear()
        data_dir = tmp_path / "data"
        for t in ("TLT", "IEF"):
            _write_cache(ParquetCache(data_dir), t, _trend_bars(60))
        reports_dir = tmp_path / "reports"

        from quant_trader.backtest.cli import main

        rc = main(
            [
                "run",
                "--strategy",
                "etf_rotation",
                "--universe",
                "alt",
                "--start",
                "2024-01-02",
                "--end",
                "2024-03-31",
                "--no-report",
                "--reports-dir",
                str(reports_dir),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "etf_rotation" in out


class TestCLIMainList:
    def _setup(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
    ) -> None:
        monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("STRATEGIES_CONFIG_PATH", str(strategies_yaml))
        monkeypatch.setenv("UNIVERSE_PRESETS_PATH", str(tmp_path / "presets.yaml"))
        (tmp_path / "presets.yaml").write_text("alt:\n  description: x\n  tickers: [TLT]\n")
        monkeypatch.setattr("quant_trader.backtest.cli.configure_logging", lambda *a, **kw: None)
        from quant_trader.core.config import get_settings

        get_settings.cache_clear()

    def test_list_empty(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._setup(monkeypatch, tmp_path, strategies_yaml)
        from quant_trader.backtest.cli import main

        rc = main(["list", "--reports-dir", str(tmp_path / "empty_reports")])
        out = capsys.readouterr().out
        assert rc == 0
        assert "Noch keine Backtests" in out

    def test_list_with_reports(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._setup(monkeypatch, tmp_path, strategies_yaml)
        reports_dir = tmp_path / "reports"
        run_dir = reports_dir / "sma_cross-2024-01-02-2024-03-31"
        run_dir.mkdir(parents=True)
        payload: dict[str, Any] = {
            "run_id": "sma_cross-2024-01-02-2024-03-31",
            "strategy_name": "sma_cross",
            "params": {},
            "start": "2024-01-02",
            "end": "2024-03-31",
            "fill_mode": "next_open",
            "initial_cash": 100000.0,
            "final_equity": 110000.0,
            "metrics": {
                "total_return_pct": 10.0,
                "cagr_pct": 5.0,
                "sharpe_ratio": 1.2,
                "max_drawdown_pct": -5.0,
                "win_rate_pct": 60.0,
                "n_trades": 5,
                "exposure_pct": 80.0,
            },
            "equity_curve": [],
            "trades": [],
        }
        (run_dir / "result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        from quant_trader.backtest.cli import main

        rc = main(["list", "--reports-dir", str(reports_dir)])
        out = capsys.readouterr().out
        assert rc == 0
        assert "RUN_ID" in out
        assert "sma_cross-2024-01-02-2024-03-31" in out
        assert "sma_cross" in out
        assert "110,000.00" in out
        assert "1.2000" in out


class TestOrchestratorDirect:
    def test_orchestrator_happy_path(
        self,
        tmp_path: Path,
        loader: StrategyLoader,
    ) -> None:
        cache = ParquetCache(tmp_path / "data")
        _write_cache(cache, "SPY", _trend_bars(60))
        reports_dir = tmp_path / "reports"
        from quant_trader.backtest.orchestrator import BacktestOrchestrator

        orchestrator = BacktestOrchestrator(cache=cache, loader=loader, reports_dir=reports_dir)
        result = orchestrator.run(
            "test-run",
            strategy_name="sma_cross",
            ticker="SPY",
            start=date(2024, 1, 2),
            end=date(2024, 3, 31),
        )
        assert result.strategy_name == "sma_cross"
        assert (reports_dir / "test-run" / "result.json").exists()

    def test_orchestrator_unknown_strategy_raises(
        self,
        tmp_path: Path,
        loader: StrategyLoader,
    ) -> None:
        from quant_trader.backtest.errors import UnknownStrategyError
        from quant_trader.backtest.orchestrator import BacktestOrchestrator

        cache = ParquetCache(tmp_path / "data")
        orchestrator = BacktestOrchestrator(
            cache=cache, loader=loader, reports_dir=tmp_path / "reports"
        )
        with pytest.raises(UnknownStrategyError) as exc_info:
            orchestrator.run(
                "rid",
                strategy_name="does_not_exist",
                ticker="SPY",
                start=date(2024, 1, 2),
                end=date(2024, 3, 31),
            )
        assert exc_info.value.name == "does_not_exist"
        assert "sma_cross" in exc_info.value.available

    def test_orchestrator_cache_missing_raises(
        self,
        tmp_path: Path,
        loader: StrategyLoader,
    ) -> None:
        from quant_trader.backtest.errors import CacheMissingError
        from quant_trader.backtest.orchestrator import BacktestOrchestrator

        cache = ParquetCache(tmp_path / "data")
        orchestrator = BacktestOrchestrator(
            cache=cache, loader=loader, reports_dir=tmp_path / "reports"
        )
        with pytest.raises(CacheMissingError) as exc_info:
            orchestrator.run(
                "rid",
                strategy_name="sma_cross",
                ticker="ZZZZ",
                start=date(2024, 1, 2),
                end=date(2024, 3, 31),
            )
        assert exc_info.value.ticker == "ZZZZ"

    def test_orchestrator_invalid_dates_raises(
        self,
        tmp_path: Path,
        loader: StrategyLoader,
    ) -> None:
        from quant_trader.backtest.errors import InvalidParamsError
        from quant_trader.backtest.orchestrator import BacktestOrchestrator

        cache = ParquetCache(tmp_path / "data")
        orchestrator = BacktestOrchestrator(
            cache=cache, loader=loader, reports_dir=tmp_path / "reports"
        )
        with pytest.raises(InvalidParamsError, match="nach end"):
            orchestrator.run(
                "rid",
                strategy_name="sma_cross",
                ticker="SPY",
                start=date(2024, 3, 31),
                end=date(2024, 1, 2),
            )

    def test_orchestrator_no_report_skips_files(
        self,
        tmp_path: Path,
        loader: StrategyLoader,
    ) -> None:
        cache = ParquetCache(tmp_path / "data")
        _write_cache(cache, "SPY", _trend_bars(60))
        reports_dir = tmp_path / "reports"
        from quant_trader.backtest.orchestrator import BacktestOrchestrator

        orchestrator = BacktestOrchestrator(cache=cache, loader=loader, reports_dir=reports_dir)
        orchestrator.run(
            "rid",
            strategy_name="sma_cross",
            ticker="SPY",
            start=date(2024, 1, 2),
            end=date(2024, 3, 31),
            write_report=False,
        )
        assert not reports_dir.exists() or list(reports_dir.iterdir()) == []
