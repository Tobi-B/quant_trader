"""Tests for Slice 4.1 - Risk-Engine: Commission, Slippage, Stop-Loss."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, ClassVar

import pytest
from structlog.testing import capture_logs

from quant_trader.backtest.engine import BacktestEngine
from quant_trader.backtest.fill import FillSimulator
from quant_trader.backtest.sizer import EqualWeightSizer
from quant_trader.backtest.types import BacktestConfig, FillMode
from quant_trader.core.types import Bar
from quant_trader.strategies.base import StrategyBase
from quant_trader.strategies.types import Action, PortfolioState, Signal


def _bar(
    close: float,
    day: int,
    open_: float | None = None,
    high: float | None = None,
    low: float | None = None,
) -> Bar:
    if open_ is None:
        open_ = close - 1.0
    if high is None:
        high = max(open_, close) + 1.0
    if low is None:
        low = min(open_, close) - 1.0
    return Bar(
        timestamp=datetime(2024, 1, 2, 16, 0) + timedelta(days=day),
        open=open_,
        high=high,
        low=low,
        close=close,
        adjusted_close=close,
        volume=1000,
    )


def _bars_from_opens(opens: list[float], closes: list[float] | None = None) -> list[Bar]:
    out: list[Bar] = []
    for i, o in enumerate(opens):
        c = closes[i] if closes else o
        out.append(_bar(close=c, day=i, open_=o))
    return out


def _bars_from_closes(closes: list[float], opens: list[float] | None = None) -> list[Bar]:
    out: list[Bar] = []
    for i, c in enumerate(closes):
        o = opens[i] if opens else c - 1.0
        out.append(_bar(close=c, day=i, open_=o))
    return out


class _BuyHoldStrategy(StrategyBase):
    name: ClassVar[str] = "buy_hold"
    version: ClassVar[str] = "1.0.0"
    default_params: ClassVar[dict[str, Any]] = {}

    def __init__(self, ticker: str = "") -> None:
        super().__init__(ticker=ticker)
        self._signaled = False

    def warmup_bars(self) -> int:
        return 0

    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
        if not self._signaled:
            self._signaled = True
            return [
                Signal(
                    timestamp=bar.timestamp,
                    ticker=self.ticker,
                    action=Action.BUY,
                    reason="entry",
                )
            ]
        return []


class _SilentStrategy(StrategyBase):
    """Emits no signals (no open positions)."""

    name: ClassVar[str] = "silent"
    version: ClassVar[str] = "1.0.0"
    default_params: ClassVar[dict[str, Any]] = {}

    def __init__(self, ticker: str = "") -> None:
        super().__init__(ticker=ticker)

    def warmup_bars(self) -> int:
        return 0

    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
        return []


class _BuyThenSellOnceStrategy(StrategyBase):
    """Buys on bar 1 (signal), sells on bar 3 (signal -> fills 4th bar)."""

    name: ClassVar[str] = "buy_then_sell_once"
    version: ClassVar[str] = "1.0.0"
    default_params: ClassVar[dict[str, Any]] = {}

    def __init__(self, ticker: str = "") -> None:
        super().__init__(ticker=ticker)
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
                    reason="entry",
                )
            ]
        if self._step == 3:
            return [
                Signal(
                    timestamp=bar.timestamp,
                    ticker=self.ticker,
                    action=Action.SELL,
                    reason="exit",
                )
            ]
        return []


def _build_config(
    cash: float = 100_000.0,
    mode: FillMode = FillMode.NEXT_OPEN,
    *,
    commission_per_trade: float = 0.0,
    commission_per_share: float = 0.0,
    slippage_pct: float = 0.0,
    stop_loss_pct: float | None = None,
) -> BacktestConfig:
    return BacktestConfig(
        initial_cash=cash,
        fill_mode=mode,
        sizer=EqualWeightSizer(),
        commission_per_trade=commission_per_trade,
        commission_per_share=commission_per_share,
        slippage_pct=slippage_pct,
        stop_loss_pct=stop_loss_pct,
    )


class TestCommissionCalculation:
    def test_commission_uses_max_at_equal(self) -> None:
        engine = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config())
        engine._commission_per_trade = 1.0
        engine._commission_per_share = 0.01
        assert engine._commission_for(100) == pytest.approx(max(1.0, 100 * 0.01))

    def test_commission_uses_per_share_when_higher(self) -> None:
        engine = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config())
        engine._commission_per_trade = 1.0
        engine._commission_per_share = 0.01
        assert engine._commission_for(500) == pytest.approx(max(1.0, 500 * 0.01))

    def test_commission_uses_per_trade_when_higher(self) -> None:
        engine = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config())
        engine._commission_per_trade = 5.0
        engine._commission_per_share = 0.01
        assert engine._commission_for(10) == pytest.approx(max(5.0, 10 * 0.01))

    def test_commission_zero_when_disabled(self) -> None:
        engine = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config())
        assert engine._commission_for(100) == pytest.approx(0.0)

    def test_commission_handles_zero_qty(self) -> None:
        engine = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config())
        engine._commission_per_trade = 5.0
        engine._commission_per_share = 0.01
        assert engine._commission_for(0) == pytest.approx(0.0)


class TestCommissionBookingInEngine:
    def test_buy_subtracts_commission_from_cash(self) -> None:
        bars = _bars_from_opens([100.0, 50.0, 51.0, 52.0, 53.0])
        engine = BacktestEngine(
            _BuyHoldStrategy("SPY"),
            _build_config(
                cash=5001.0,
                commission_per_trade=1.0,
                commission_per_share=0.0,
            ),
        )
        result = engine.run({"SPY": bars})
        buy_snapshot = result.equity_curve[2]
        assert buy_snapshot.positions == {"SPY": 100}
        assert buy_snapshot.cash == pytest.approx(0.0)

    def test_sell_adds_proceeds_minus_commission(self) -> None:
        bars = _bars_from_opens([100.0, 50.0, 51.0, 55.0, 56.0])
        engine = BacktestEngine(
            _BuyThenSellOnceStrategy("SPY"),
            _build_config(
                cash=5001.0,
                commission_per_trade=1.0,
                commission_per_share=0.0,
            ),
        )
        result = engine.run({"SPY": bars})
        sell_snapshot = result.equity_curve[4]
        assert sell_snapshot.positions == {}
        assert sell_snapshot.cash == pytest.approx(5500.0 - 1.0)

    def test_trade_pnl_includes_commissions(self) -> None:
        bars = _bars_from_opens([100.0, 50.0, 51.0, 55.0, 56.0])
        engine = BacktestEngine(
            _BuyThenSellOnceStrategy("SPY"),
            _build_config(
                cash=5001.0,
                commission_per_trade=1.0,
                commission_per_share=0.0,
            ),
        )
        result = engine.run({"SPY": bars})
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.entry_price == pytest.approx(50.0)
        assert trade.exit_price == pytest.approx(55.0)
        assert trade.pnl == pytest.approx(5500.0 - 1.0 - (5000.0 + 1.0))

    def test_fill_fee_field_set(self) -> None:
        bars = _bars_from_opens([100.0, 50.0, 51.0, 52.0, 53.0])
        engine = BacktestEngine(
            _BuyHoldStrategy("SPY"),
            _build_config(
                cash=5001.0,
                commission_per_trade=1.5,
                commission_per_share=0.0,
            ),
        )
        with capture_logs() as logs:
            engine.run({"SPY": bars})
        buy_logs = [entry for entry in logs if entry["event"] == "backtest.buy_filled"]
        assert len(buy_logs) == 1
        assert buy_logs[0]["fee"] == pytest.approx(1.5)


class TestSlippageInFillSimulator:
    @staticmethod
    def _slippage_helper(slip: float, raw_price: float) -> tuple[float, float]:
        bar = Bar(
            timestamp=datetime(2024, 1, 2, 16, 0),
            open=raw_price,
            high=raw_price + 1.0,
            low=raw_price - 1.0,
            close=raw_price,
            adjusted_close=raw_price,
            volume=1000,
        )
        sim_buy = FillSimulator(FillMode.SAME_CLOSE, slippage_pct=slip)
        sim_sell = FillSimulator(FillMode.SAME_CLOSE, slippage_pct=slip)
        sig_buy = Signal(timestamp=bar.timestamp, ticker="SPY", action=Action.BUY)
        sig_sell = Signal(timestamp=bar.timestamp, ticker="SPY", action=Action.SELL)
        fill_buy = sim_buy.resolve(sim_buy.schedule(sig_buy, [bar], 0))
        fill_sell = sim_sell.resolve(sim_sell.schedule(sig_sell, [bar], 0))
        return (fill_buy.price, fill_sell.price)

    def test_slippage_buy_increases_price(self) -> None:
        buy_price, _ = self._slippage_helper(0.1, 100.0)
        assert buy_price == pytest.approx(100.0 * 1.001)

    def test_slippage_sell_decreases_price(self) -> None:
        _, sell_price = self._slippage_helper(0.1, 100.0)
        assert sell_price == pytest.approx(100.0 * 0.999)

    def test_no_slippage_unchanged(self) -> None:
        buy_price, sell_price = self._slippage_helper(0.0, 100.0)
        assert buy_price == pytest.approx(100.0)
        assert sell_price == pytest.approx(100.0)

    def test_slippage_higher_pct(self) -> None:
        buy_price, sell_price = self._slippage_helper(1.0, 200.0)
        assert buy_price == pytest.approx(202.0)
        assert sell_price == pytest.approx(198.0)

    def test_slippage_default_zero_on_resolve(self) -> None:
        bar = Bar(
            timestamp=datetime(2024, 1, 2, 16, 0),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            adjusted_close=100.0,
            volume=1000,
        )
        sim = FillSimulator(FillMode.SAME_CLOSE)
        sig = Signal(timestamp=bar.timestamp, ticker="SPY", action=Action.BUY)
        fill = sim.resolve(sim.schedule(sig, [bar], 0))
        assert fill.price == pytest.approx(100.0)


class TestStopLoss:
    def test_stop_loss_triggers_on_open_below_threshold(self) -> None:
        bars = _bars_from_opens([100.0, 100.0, 94.0, 99.0, 98.0])
        engine = BacktestEngine(
            _BuyHoldStrategy("SPY"),
            _build_config(stop_loss_pct=5.0),
        )
        result = engine.run({"SPY": bars})
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.entry_price == pytest.approx(100.0)
        assert trade.exit_price == pytest.approx(99.0)

    def test_stop_loss_does_not_trigger_above_threshold(self) -> None:
        bars = _bars_from_opens([100.0, 100.0, 96.0, 97.0, 98.0])
        engine = BacktestEngine(
            _BuyHoldStrategy("SPY"),
            _build_config(stop_loss_pct=5.0),
        )
        result = engine.run({"SPY": bars})
        assert result.trades == []
        assert result.equity_curve[-1].positions.get("SPY", 0) >= 1

    def test_stop_loss_disabled_when_none(self) -> None:
        bars = _bars_from_opens([100.0, 100.0, 50.0, 50.0, 50.0])
        engine = BacktestEngine(
            _BuyHoldStrategy("SPY"),
            _build_config(stop_loss_pct=None),
        )
        result = engine.run({"SPY": bars})
        assert result.trades == []
        assert result.equity_curve[-1].positions.get("SPY", 0) >= 1

    def test_stop_loss_only_long_positions(self) -> None:
        bars = _bars_from_opens([100.0, 50.0, 40.0, 41.0, 42.0])
        engine = BacktestEngine(
            _SilentStrategy("SPY"),
            _build_config(stop_loss_pct=5.0),
        )
        result = engine.run({"SPY": bars})
        assert result.trades == []
        assert result.equity_curve[-1].positions == {}

    def test_stop_loss_logs_warning(self) -> None:
        bars = _bars_from_opens([100.0, 100.0, 94.0, 99.0, 98.0])
        engine = BacktestEngine(
            _BuyHoldStrategy("SPY"),
            _build_config(stop_loss_pct=5.0),
        )
        with capture_logs() as logs:
            engine.run({"SPY": bars})
        stop_logs = [entry for entry in logs if entry["event"] == "backtest.stop_loss"]
        assert len(stop_logs) == 1
        log_entry = stop_logs[0]
        assert log_entry["ticker"] == "SPY"
        assert log_entry["entry_price"] == pytest.approx(100.0)
        assert log_entry["trigger_price"] == pytest.approx(94.0)
        assert log_entry["stop_loss_pct"] == pytest.approx(5.0)


class TestRiskIntegration:
    def test_full_scenario_buy_hold_drop_stop_loss(self) -> None:
        bars = _bars_from_opens([100.0, 100.0, 90.0, 99.0, 98.0])
        engine = BacktestEngine(
            _BuyHoldStrategy("SPY"),
            _build_config(stop_loss_pct=5.0),
        )
        result = engine.run({"SPY": bars})
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.entry_price == pytest.approx(100.0)
        assert trade.exit_price == pytest.approx(99.0)
        assert trade.pnl < 0

    def test_backward_compat_all_defaults_zero(self) -> None:
        bars = _bars_from_closes([100.0] * 8, opens=[99.0] * 8)
        engine_default = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config())
        result_default = engine_default.run({"SPY": bars})
        cfg_explicit_zero = BacktestConfig(
            initial_cash=100_000.0,
            fill_mode=FillMode.NEXT_OPEN,
            sizer=EqualWeightSizer(),
            commission_per_trade=0.0,
            commission_per_share=0.0,
            slippage_pct=0.0,
            stop_loss_pct=None,
        )
        engine_explicit = BacktestEngine(_BuyHoldStrategy("SPY"), cfg_explicit_zero)
        result_explicit = engine_explicit.run({"SPY": bars})
        assert result_default.final_equity == pytest.approx(result_explicit.final_equity)
        assert result_default.equity_curve == result_explicit.equity_curve

    def test_total_commission_logged_in_complete_event(self) -> None:
        bars = _bars_from_opens([100.0, 50.0, 51.0, 55.0, 56.0])
        engine = BacktestEngine(
            _BuyThenSellOnceStrategy("SPY"),
            _build_config(
                cash=5001.0,
                commission_per_trade=1.0,
                commission_per_share=0.0,
            ),
        )
        with capture_logs() as logs:
            engine.run({"SPY": bars})
        complete_logs = [entry for entry in logs if entry["event"] == "backtest.complete"]
        assert len(complete_logs) == 1
        assert complete_logs[0]["total_commission"] == pytest.approx(2.0)
        assert complete_logs[0]["stop_loss_count"] == 0

    def test_stop_loss_count_logged_in_complete_event(self) -> None:
        bars = _bars_from_opens([100.0, 100.0, 94.0, 99.0, 98.0])
        engine = BacktestEngine(
            _BuyHoldStrategy("SPY"),
            _build_config(stop_loss_pct=5.0),
        )
        with capture_logs() as logs:
            engine.run({"SPY": bars})
        complete_logs = [entry for entry in logs if entry["event"] == "backtest.complete"]
        assert len(complete_logs) == 1
        assert complete_logs[0]["stop_loss_count"] == 1
        assert complete_logs[0]["total_commission"] == pytest.approx(0.0)
