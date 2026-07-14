"""Tests for MetricsCalculator and helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, ClassVar

import pytest

from quant_trader.backtest.engine import BacktestEngine
from quant_trader.backtest.metrics import (
    EquityCurveStats,
    Metrics,
    MetricsCalculator,
    TradeStats,
)
from quant_trader.backtest.sizer import EqualWeightSizer
from quant_trader.backtest.types import (
    BacktestConfig,
    BacktestResult,
    EquitySnapshot,
    FillMode,
    Trade,
)
from quant_trader.core.types import Bar
from quant_trader.strategies.base import StrategyBase
from quant_trader.strategies.types import Action, PortfolioState, Signal


def _snapshot(
    d: date, equity: float, cash: float, positions: dict[str, int] | None = None
) -> EquitySnapshot:
    return EquitySnapshot(
        date=d,
        equity=equity,
        cash=cash,
        positions=positions if positions is not None else {},
    )


def _bars_flat(n: int = 30, close: float = 100.0) -> list[Bar]:
    return [
        Bar(
            timestamp=datetime(2024, 1, 2, 16, 0) + timedelta(days=i),
            open=close,
            high=close,
            low=close,
            close=close,
            adjusted_close=close,
            volume=1000,
        )
        for i in range(n)
    ]


def _build_result(
    snapshots: list[EquitySnapshot],
    trades: list[Trade] | None = None,
    initial_cash: float = 100_000.0,
) -> BacktestResult:
    return BacktestResult(
        strategy_name="test",
        params={},
        start=snapshots[0].date if snapshots else date(2024, 1, 2),
        end=snapshots[-1].date if snapshots else date(2024, 1, 2),
        fill_mode=FillMode.NEXT_OPEN,
        initial_cash=initial_cash,
        final_equity=snapshots[-1].equity if snapshots else initial_cash,
        trades=trades or [],
        equity_curve=snapshots,
    )


def _trade(pnl: float, ticker: str = "SPY") -> Trade:
    return Trade(
        ticker=ticker,
        entry_date=date(2024, 1, 5),
        entry_price=100.0,
        exit_date=date(2024, 1, 10),
        exit_price=100.0 + pnl,
        pnl=pnl,
        pnl_pct=pnl / 100.0,
    )


class TestEquityCurveStats:
    def test_compute_returns_empty(self) -> None:
        assert EquityCurveStats().compute_returns([]) == []

    def test_compute_returns_single(self) -> None:
        snaps = [_snapshot(date(2024, 1, 1), 100.0, 100.0)]
        assert EquityCurveStats().compute_returns(snaps) == [0.0]

    def test_compute_returns_up(self) -> None:
        snaps = [
            _snapshot(date(2024, 1, 1), 100.0, 100.0),
            _snapshot(date(2024, 1, 2), 110.0, 100.0),
            _snapshot(date(2024, 1, 3), 121.0, 100.0),
        ]
        returns = EquityCurveStats().compute_returns(snaps)
        assert returns[0] == 0.0
        assert returns[1] == pytest.approx(0.1)
        assert returns[2] == pytest.approx(0.1)

    def test_cagr_empty(self) -> None:
        assert EquityCurveStats().cagr_pct([], 100_000.0) == 0.0

    def test_cagr_single_snapshot(self) -> None:
        snaps = [_snapshot(date(2024, 1, 1), 100_000.0, 100_000.0)]
        assert EquityCurveStats().cagr_pct(snaps, 100_000.0) == 0.0

    def test_cagr_one_year_doubles(self) -> None:
        snaps = [
            _snapshot(date(2024, 1, 1) + timedelta(days=i), 100_000.0 + i * (100_000.0 / 252), 0.0)
            for i in range(253)
        ]
        cagr = EquityCurveStats().cagr_pct(snaps, 100_000.0)
        assert cagr == pytest.approx(100.0, abs=0.5)

    def test_cagr_flat(self) -> None:
        snaps = [
            _snapshot(date(2024, 1, 1) + timedelta(days=i), 100_000.0, 100_000.0)
            for i in range(252)
        ]
        assert EquityCurveStats().cagr_pct(snaps, 100_000.0) == pytest.approx(0.0, abs=0.01)

    def test_sharpe_empty(self) -> None:
        assert EquityCurveStats().sharpe([]) is None

    def test_sharpe_single_return(self) -> None:
        assert EquityCurveStats().sharpe([0.01]) is None

    def test_sharpe_flat_zero_std(self) -> None:
        assert EquityCurveStats().sharpe([0.0, 0.0, 0.0]) is None

    def test_sharpe_simple_positive(self) -> None:
        returns = [0.01] * 252
        sharpe = EquityCurveStats().sharpe(returns)
        assert sharpe is None

    def test_sharpe_with_variance(self) -> None:
        returns = [0.01, -0.01, 0.01, -0.01] * 63
        returns.append(0.0)
        sharpe = EquityCurveStats().sharpe(returns)
        assert sharpe is not None
        assert sharpe == pytest.approx(0.0, abs=0.01)

    def test_max_drawdown_empty(self) -> None:
        assert EquityCurveStats().max_drawdown_pct([]) == 0.0

    def test_max_drawdown_monotonic_up(self) -> None:
        snaps = [_snapshot(date(2024, 1, 1) + timedelta(days=i), 100.0 + i, 0.0) for i in range(10)]
        assert EquityCurveStats().max_drawdown_pct(snaps) == 0.0

    def test_max_drawdown_simple(self) -> None:
        snaps = [
            _snapshot(date(2024, 1, 1), 100.0, 0.0),
            _snapshot(date(2024, 1, 2), 120.0, 0.0),
            _snapshot(date(2024, 1, 3), 60.0, 0.0),
        ]
        assert EquityCurveStats().max_drawdown_pct(snaps) == pytest.approx(50.0)

    def test_max_drawdown_v_shape(self) -> None:
        snaps = [
            _snapshot(date(2024, 1, 1), 100.0, 0.0),
            _snapshot(date(2024, 1, 2), 50.0, 0.0),
            _snapshot(date(2024, 1, 3), 100.0, 0.0),
            _snapshot(date(2024, 1, 4), 75.0, 0.0),
        ]
        assert EquityCurveStats().max_drawdown_pct(snaps) == pytest.approx(50.0)

    def test_exposure_empty(self) -> None:
        assert EquityCurveStats().exposure_pct([]) == 0.0

    def test_exposure_all_flat(self) -> None:
        snaps = [_snapshot(date(2024, 1, 1) + timedelta(days=i), 100.0, 100.0) for i in range(5)]
        assert EquityCurveStats().exposure_pct(snaps) == 0.0

    def test_exposure_all_invested(self) -> None:
        snaps = [
            _snapshot(date(2024, 1, 1) + timedelta(days=i), 100.0, 0.0, {"SPY": 1})
            for i in range(5)
        ]
        assert EquityCurveStats().exposure_pct(snaps) == 100.0

    def test_exposure_mixed(self) -> None:
        snaps = [
            _snapshot(date(2024, 1, 1), 100.0, 100.0),
            _snapshot(date(2024, 1, 2), 100.0, 0.0, {"SPY": 1}),
            _snapshot(date(2024, 1, 3), 100.0, 100.0),
            _snapshot(date(2024, 1, 4), 100.0, 0.0, {"SPY": 1}),
        ]
        assert EquityCurveStats().exposure_pct(snaps) == 50.0


class TestTradeStats:
    def test_win_rate_empty(self) -> None:
        assert TradeStats().win_rate_pct([]) is None

    def test_win_rate_one_trade(self) -> None:
        assert TradeStats().win_rate_pct([_trade(50.0)]) is None

    def test_win_rate_one_win_one_loss(self) -> None:
        wr = TradeStats().win_rate_pct([_trade(50.0), _trade(-30.0)])
        assert wr == pytest.approx(50.0)

    def test_win_rate_all_win(self) -> None:
        wr = TradeStats().win_rate_pct([_trade(10.0), _trade(20.0), _trade(5.0)])
        assert wr == pytest.approx(100.0)

    def test_win_rate_all_loss(self) -> None:
        wr = TradeStats().win_rate_pct([_trade(-10.0), _trade(-20.0)])
        assert wr == pytest.approx(0.0)

    def test_win_rate_ignores_zero_pnl(self) -> None:
        wr = TradeStats().win_rate_pct([_trade(10.0), _trade(0.0)])
        assert wr == pytest.approx(50.0)


class TestMetricsCalculator:
    def test_empty_run(self) -> None:
        snaps = [_snapshot(date(2024, 1, 1), 100_000.0, 100_000.0)]
        result = _build_result(snaps)
        metrics = MetricsCalculator().calculate(result)
        assert isinstance(metrics, Metrics)
        assert metrics.n_trades == 0
        assert metrics.total_return_pct == 0.0
        assert metrics.cagr_pct == 0.0
        assert metrics.sharpe_ratio is None
        assert metrics.max_drawdown_pct == 0.0
        assert metrics.win_rate_pct is None
        assert metrics.exposure_pct == 0.0

    def test_zero_snapshots(self) -> None:
        result = _build_result([])
        metrics = MetricsCalculator().calculate(result)
        assert metrics.n_trades == 0
        assert metrics.total_return_pct == 0.0
        assert metrics.cagr_pct == 0.0
        assert metrics.sharpe_ratio is None
        assert metrics.max_drawdown_pct == 0.0
        assert metrics.exposure_pct == 0.0

    def test_one_trade_sharpe_none(self) -> None:
        snaps = [_snapshot(date(2024, 1, 1) + timedelta(days=i), 100_000.0, 0.0) for i in range(10)]
        result = _build_result(snaps, trades=[_trade(50.0)])
        metrics = MetricsCalculator().calculate(result)
        assert metrics.n_trades == 1
        assert metrics.sharpe_ratio is None
        assert metrics.win_rate_pct is None

    def test_two_trades_sharpe_set(self) -> None:
        snaps = [
            _snapshot(date(2024, 1, 1) + timedelta(days=i), 100_000.0 + i * 10, 0.0)
            for i in range(10)
        ]
        result = _build_result(snaps, trades=[_trade(50.0), _trade(-20.0)])
        metrics = MetricsCalculator().calculate(result)
        assert metrics.n_trades == 2
        assert metrics.sharpe_ratio is not None
        assert metrics.win_rate_pct == pytest.approx(50.0)

    def test_total_return_positive(self) -> None:
        snaps = [
            _snapshot(date(2024, 1, 1), 100_000.0, 100_000.0),
            _snapshot(date(2024, 1, 2), 120_000.0, 100_000.0),
        ]
        result = _build_result(snaps, initial_cash=100_000.0)
        metrics = MetricsCalculator().calculate(result)
        assert metrics.total_return_pct == pytest.approx(20.0)

    def test_total_return_negative(self) -> None:
        snaps = [
            _snapshot(date(2024, 1, 1), 100_000.0, 100_000.0),
            _snapshot(date(2024, 1, 2), 80_000.0, 100_000.0),
        ]
        result = _build_result(snaps, initial_cash=100_000.0)
        metrics = MetricsCalculator().calculate(result)
        assert metrics.total_return_pct == pytest.approx(-20.0)

    def test_metrics_is_frozen(self) -> None:
        snaps = [_snapshot(date(2024, 1, 1), 100_000.0, 100_000.0)]
        result = _build_result(snaps)
        metrics = MetricsCalculator().calculate(result)
        with pytest.raises((AttributeError, Exception)):
            metrics.n_trades = 99  # type: ignore[misc]


class TestMetricsCalculatorIntegration:
    def test_metrics_from_real_engine_run(self) -> None:
        class _BuySellStrategy(StrategyBase):
            name: ClassVar[str] = "buy_sell"
            version: ClassVar[str] = "1.0.0"
            default_params: ClassVar[dict[str, Any]] = {}

            def __init__(self, ticker: str = "", params: dict[str, Any] | None = None) -> None:
                super().__init__(ticker=ticker, params=params)
                self._step = 0

            def warmup_bars(self) -> int:
                return 0

            def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
                self._step += 1
                if self._step == 1:
                    return [
                        Signal(
                            timestamp=bar.timestamp,
                            ticker=self.ticker,
                            action=Action.BUY,
                            reason="e",
                        )
                    ]
                if self._step == 5:
                    return [
                        Signal(
                            timestamp=bar.timestamp,
                            ticker=self.ticker,
                            action=Action.SELL,
                            reason="x",
                        )
                    ]
                return []

        bars = _bars_flat(n=10, close=100.0)
        engine = BacktestEngine(
            _BuySellStrategy("SPY"),
            BacktestConfig(
                initial_cash=100_000.0, fill_mode=FillMode.NEXT_OPEN, sizer=EqualWeightSizer()
            ),
        )
        bt_result = engine.run({"SPY": bars})
        metrics = MetricsCalculator().calculate(bt_result)
        assert metrics.n_trades == 1
        assert metrics.total_return_pct == pytest.approx(0.0)
        assert metrics.sharpe_ratio is None
        assert metrics.max_drawdown_pct == 0.0
