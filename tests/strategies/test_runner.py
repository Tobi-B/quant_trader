"""Tests for SignalRunner and SignalFormatter."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from quant_trader.core.types import Bar, Granularity
from quant_trader.data.cache import ParquetCache
from quant_trader.strategies import (
    Action,
    Signal,
    SignalFormatter,
    SignalRunner,
    SmaCrossStrategy,
)
from quant_trader.strategies.errors import (
    StrategyConfigError,
    UnknownStrategyError,
)
from quant_trader.strategies.loader import StrategyLoader


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


@pytest.fixture
def cache(tmp_path: Path) -> ParquetCache:
    return ParquetCache(tmp_path)


@pytest.fixture
def strategies_yaml(tmp_path: Path) -> Path:
    cfg = tmp_path / "strategies.yaml"
    cfg.write_text(
        "sma_cross:\n  params: {fast: 5, slow: 10}\n"
        "rsi_mean_reversion:\n  params: {period: 5, oversold: 30.0, overbought: 70.0}\n",
        encoding="utf-8",
    )
    return cfg


@pytest.fixture
def loader(strategies_yaml: Path) -> StrategyLoader:
    ldr = StrategyLoader(strategies_yaml)
    ldr.register(SmaCrossStrategy)
    return ldr


class TestSignalFormatter:
    def test_empty_signals_returns_message(self) -> None:
        out = SignalFormatter().format_signals([])
        assert out == "no signals"

    def test_single_signal_renders_table(self) -> None:
        sig = Signal(
            timestamp=datetime(2024, 1, 2, 16, 0),
            ticker="SPY",
            action=Action.BUY,
            reason="sma_cross_up",
        )
        out = SignalFormatter().format_signals([sig])
        lines = out.splitlines()
        assert lines[0].startswith("TIMESTAMP")
        for header in ("TIMESTAMP", "TICKER", "ACTION", "REASON"):
            assert header in lines[0]
        assert lines[1].startswith("---") and "+" in lines[1]
        assert "SPY" in lines[2]
        assert "BUY" in lines[2]
        assert "sma_cross_up" in lines[2]

    def test_limit_caps_rows_and_adds_footer(self) -> None:
        sigs = [
            Signal(
                timestamp=datetime(2024, 1, 2, 16, 0) + timedelta(days=i),
                ticker="SPY",
                action=Action.BUY,
                reason="x",
            )
            for i in range(5)
        ]
        out = SignalFormatter().format_signals(sigs, limit=2)
        lines = out.splitlines()
        data_rows = [ln for ln in lines[2:] if not ln.startswith("...")]
        assert len(data_rows) == 2
        assert lines[-1] == "... 3 more"

    def test_limit_larger_than_count_no_footer(self) -> None:
        sig = Signal(
            timestamp=datetime(2024, 1, 2, 16, 0),
            ticker="SPY",
            action=Action.SELL,
            reason="r",
        )
        out = SignalFormatter().format_signals([sig], limit=10)
        assert "... " not in out


class TestSignalRunnerSingle:
    def test_happy_path_returns_signals(self, cache: ParquetCache, loader: StrategyLoader) -> None:
        _write_cache(cache, "SPY", _trend_bars(60))
        runner = SignalRunner(cache=cache, loader=loader)
        signals = runner.run(
            "sma_cross",
            ticker="SPY",
            start=date(2024, 1, 1),
            end=date(2024, 6, 30),
        )
        assert isinstance(signals, list)
        for s in signals:
            assert s.ticker == "SPY"
            assert s.action in (Action.BUY, Action.SELL, Action.HOLD)

    def test_missing_cache_raises_file_not_found(
        self, cache: ParquetCache, loader: StrategyLoader
    ) -> None:
        runner = SignalRunner(cache=cache, loader=loader)
        with pytest.raises(FileNotFoundError, match="Kein Cache"):
            runner.run(
                "sma_cross",
                ticker="ZZZZ",
                start=date(2024, 1, 1),
                end=date(2024, 1, 31),
            )

    def test_single_ticker_without_ticker_raises(
        self, cache: ParquetCache, loader: StrategyLoader
    ) -> None:
        runner = SignalRunner(cache=cache, loader=loader)
        with pytest.raises(StrategyConfigError, match="--ticker ist erforderlich"):
            runner.run(
                "sma_cross",
                start=date(2024, 1, 1),
                end=date(2024, 1, 31),
            )


class TestSignalRunnerMulti:
    def test_multi_ticker_uses_params_universe(self, tmp_path: Path, cache: ParquetCache) -> None:
        cfg = tmp_path / "strategies.yaml"
        cfg.write_text(
            "etf_rotation:\n  params:\n    universe: [SPY, AGG]\n    top_n: 1\n    "
            "lookback_months: 1\n    rebalance_freq: monthly\n",
            encoding="utf-8",
        )
        from quant_trader.strategies import EtfRotationStrategy

        ldr = StrategyLoader(cfg)
        ldr.register(EtfRotationStrategy)
        for t in ("SPY", "AGG"):
            _write_cache(cache, t, _trend_bars(60))
        runner = SignalRunner(cache=cache, loader=ldr)
        signals = runner.run(
            "etf_rotation",
            start=date(2024, 1, 1),
            end=date(2024, 6, 30),
        )
        assert isinstance(signals, list)

    def test_multi_ticker_universe_override_via_preset(
        self, tmp_path: Path, cache: ParquetCache
    ) -> None:
        cfg = tmp_path / "strategies.yaml"
        cfg.write_text(
            "etf_rotation:\n  params:\n    universe: [SPY, AGG]\n    top_n: 1\n    "
            "lookback_months: 1\n    rebalance_freq: monthly\n",
            encoding="utf-8",
        )
        presets = tmp_path / "presets.yaml"
        presets.write_text("alt:\n  description: x\n  tickers: [TLT, IEF]\n", encoding="utf-8")
        import os

        os.environ["UNIVERSE_PRESETS_PATH"] = str(presets)
        os.environ["STRATEGIES_CONFIG_PATH"] = str(cfg)
        from quant_trader.core.config import get_settings

        get_settings.cache_clear()

        from quant_trader.strategies import EtfRotationStrategy

        ldr = StrategyLoader(cfg)
        ldr.register(EtfRotationStrategy)
        for t in ("TLT", "IEF"):
            _write_cache(cache, t, _trend_bars(60))
        runner = SignalRunner(cache=cache, loader=ldr)
        signals = runner.run(
            "etf_rotation",
            universe="alt",
            start=date(2024, 1, 1),
            end=date(2024, 6, 30),
        )
        assert isinstance(signals, list)

    def test_unknown_strategy_raises(self, cache: ParquetCache, loader: StrategyLoader) -> None:
        runner = SignalRunner(cache=cache, loader=loader)
        with pytest.raises(UnknownStrategyError):
            runner.run(
                "does_not_exist",
                ticker="SPY",
                start=date(2024, 1, 1),
                end=date(2024, 1, 31),
            )


class TestSignalRunnerCLIParser:
    def test_parser_requires_command(self) -> None:
        from quant_trader.strategies.cli import build_parser

        with pytest.raises(SystemExit):
            build_parser().parse_args([])

    def test_parser_run_minimal(self) -> None:
        from quant_trader.strategies.cli import build_parser

        ns = build_parser().parse_args(["run", "--strategy", "sma_cross", "--ticker", "SPY"])
        assert ns.command == "run"
        assert ns.strategy == "sma_cross"
        assert ns.ticker == "SPY"
        assert ns.granularity == "daily"
        assert ns.limit == 100

    def test_parser_list_command(self) -> None:
        from quant_trader.strategies.cli import build_parser

        ns = build_parser().parse_args(["list"])
        assert ns.command == "list"


class TestSignalRunnerCLI:
    def _setup_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
    ) -> None:
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("STRATEGIES_CONFIG_PATH", str(strategies_yaml))
        monkeypatch.setattr("quant_trader.strategies.cli.configure_logging", lambda *a, **kw: None)

    def test_cli_returns_1_for_unknown_strategy(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, strategies_yaml: Path
    ) -> None:
        self._setup_env(monkeypatch, tmp_path, strategies_yaml)
        from quant_trader.core.config import get_settings
        from quant_trader.strategies.cli import main

        get_settings.cache_clear()
        rc = main(["run", "--strategy", "does_not_exist", "--ticker", "SPY"])
        assert rc == 1

    def test_cli_returns_1_when_cache_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, strategies_yaml: Path
    ) -> None:
        self._setup_env(monkeypatch, tmp_path, strategies_yaml)
        from quant_trader.core.config import get_settings
        from quant_trader.strategies.cli import main

        get_settings.cache_clear()
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
                "2024-01-10",
            ]
        )
        assert rc == 1

    def test_cli_returns_0_and_prints_table(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
        cache: ParquetCache,
    ) -> None:
        self._setup_env(monkeypatch, tmp_path, strategies_yaml)
        _write_cache(cache, "SPY", _trend_bars(60))
        from quant_trader.core.config import get_settings
        from quant_trader.strategies.cli import main

        get_settings.cache_clear()
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
            ]
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert "TIMESTAMP" in out
        assert "TICKER" in out
        assert "ACTION" in out

    def test_cli_list_prints_strategies(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        strategies_yaml: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._setup_env(monkeypatch, tmp_path, strategies_yaml)
        from quant_trader.core.config import get_settings
        from quant_trader.strategies.cli import main

        get_settings.cache_clear()
        rc = main(["list"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "sma_cross" in out
