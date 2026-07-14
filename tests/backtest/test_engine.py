"""Tests for BacktestEngine: end-to-end backtest simulation."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, ClassVar

import pytest

from quant_trader.backtest.engine import BacktestEngine
from quant_trader.backtest.errors import BacktestConfigError
from quant_trader.backtest.sizer import EqualWeightSizer
from quant_trader.backtest.types import BacktestConfig, FillMode
from quant_trader.core.types import Bar
from quant_trader.strategies.base import StrategyBase
from quant_trader.strategies.types import Action, PortfolioState, Signal


def _bar(close: float, day: int, open_: float | None = None) -> Bar:
    if open_ is None:
        open_ = close - 1.0
    return Bar(
        timestamp=datetime(2024, 1, 2, 16, 0) + timedelta(days=day),
        open=open_,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        adjusted_close=close,
        volume=1000,
    )


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

    def __init__(self, ticker: str = "", params: dict[str, Any] | None = None) -> None:
        super().__init__(ticker=ticker, params=params)
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
                    reason="entry",
                )
            ]
        if self._step == 5:
            return [
                Signal(
                    timestamp=bar.timestamp,
                    ticker=self.ticker,
                    action=Action.SELL,
                    reason="exit",
                )
            ]
        return []


class _BuyOnlyStrategy(StrategyBase):
    name: ClassVar[str] = "buy_only"
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
                    reason="e1",
                )
            ]
        if self._step == 2:
            return [
                Signal(
                    timestamp=bar.timestamp,
                    ticker=self.ticker,
                    action=Action.BUY,
                    reason="e2",
                )
            ]
        return []


def _build_config(cash: float = 100_000.0, mode: FillMode = FillMode.NEXT_OPEN) -> BacktestConfig:
    return BacktestConfig(
        initial_cash=cash,
        fill_mode=mode,
        sizer=EqualWeightSizer(),
    )


class TestBacktestEngineConfig:
    def test_invalid_initial_cash_raises(self) -> None:
        with pytest.raises(BacktestConfigError, match="initial_cash"):
            BacktestEngine(_BuyHoldStrategy("SPY"), _build_config(cash=0))

    def test_invalid_sizer_raises(self) -> None:
        bad_config = BacktestConfig(initial_cash=100.0, fill_mode=FillMode.NEXT_OPEN, sizer=42)
        with pytest.raises(BacktestConfigError, match="allocate"):
            BacktestEngine(_BuyHoldStrategy("SPY"), bad_config)

    def test_empty_bars_raises(self) -> None:
        engine = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config())
        with pytest.raises(BacktestConfigError, match="leer"):
            engine.run({})

    def test_bars_for_unknown_ticker_raises(self) -> None:
        engine = BacktestEngine(_BuyHoldStrategy("ZZZZ"), _build_config())
        with pytest.raises(BacktestConfigError, match="ZZZZ"):
            engine.run({"SPY": _bars_from_closes([100.0] * 5)})

    def test_single_ticker_without_strategy_ticker_raises(self) -> None:
        engine = BacktestEngine(_BuyHoldStrategy(""), _build_config())
        with pytest.raises(BacktestConfigError, match="ticker"):
            engine.run({"SPY": _bars_from_closes([100.0] * 5)})


class TestBacktestEngineSingleTicker:
    def test_happy_path_buy_then_sell_records_trade(self) -> None:
        closes = [100.0, 100.0, 100.0, 100.0, 100.0, 110.0, 120.0, 130.0]
        opens = [c - 1.0 for c in closes]
        bars = _bars_from_closes(closes, opens)
        engine = BacktestEngine(_BuySellStrategy("SPY"), _build_config())
        result = engine.run({"SPY": bars})

        assert result.strategy_name == "buy_sell"
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.ticker == "SPY"
        assert trade.entry_price == pytest.approx(opens[1])
        assert trade.exit_price == pytest.approx(opens[5])

    def test_rebuy_noop_logs(self) -> None:
        closes = [100.0] * 8
        opens = [c - 1.0 for c in closes]
        bars = _bars_from_closes(closes, opens)
        engine = BacktestEngine(_BuyOnlyStrategy("SPY"), _build_config())
        result = engine.run({"SPY": bars})
        assert result.trades == []
        assert all(snap.positions.get("SPY", 0) == 1010 for snap in result.equity_curve[1:])

    def test_sell_without_position_is_noop(self) -> None:
        closes = [100.0] * 8
        opens = [c - 1.0 for c in closes]
        bars = _bars_from_closes(closes, opens)

        class _SellOnly(StrategyBase):
            name: ClassVar[str] = "sell_only"
            version: ClassVar[str] = "1.0.0"
            default_params: ClassVar[dict[str, Any]] = {}

            def __init__(self, ticker: str = "", params: dict[str, Any] | None = None) -> None:
                super().__init__(ticker=ticker, params=params)

            def warmup_bars(self) -> int:
                return 0

            def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
                return [
                    Signal(
                        timestamp=bar.timestamp,
                        ticker=self.ticker,
                        action=Action.SELL,
                        reason="no_pos",
                    )
                ]

        engine = BacktestEngine(_SellOnly("SPY"), _build_config())
        result = engine.run({"SPY": bars})
        assert result.trades == []
        assert result.final_equity == pytest.approx(100_000.0)

    def test_insufficient_cash_skips(self) -> None:
        closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
        opens = [c - 1.0 for c in closes]
        bars = _bars_from_closes(closes, opens)
        engine = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config(cash=0.5))
        result = engine.run({"SPY": bars})
        assert result.trades == []

    def test_equity_curve_length_matches_bar_count(self) -> None:
        bars = _bars_from_closes([100.0] * 10)
        engine = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config())
        result = engine.run({"SPY": bars})
        assert len(result.equity_curve) == len(bars)

    def test_same_close_mode_fills_at_signal_close(self) -> None:
        closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
        opens = [c - 1.0 for c in closes]
        bars = _bars_from_closes(closes, opens)
        engine = BacktestEngine(_BuySellStrategy("SPY"), _build_config(mode=FillMode.SAME_CLOSE))
        result = engine.run({"SPY": bars})
        assert len(result.trades) == 1
        assert result.trades[0].entry_price == pytest.approx(100.0)
        assert result.trades[0].exit_price == pytest.approx(100.0)

    def test_no_signals_zero_trades(self) -> None:
        class _Silent(StrategyBase):
            name: ClassVar[str] = "silent"
            version: ClassVar[str] = "1.0.0"
            default_params: ClassVar[dict[str, Any]] = {}

            def __init__(self, ticker: str = "", params: dict[str, Any] | None = None) -> None:
                super().__init__(ticker=ticker, params=params)

            def warmup_bars(self) -> int:
                return 0

            def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
                return []

        bars = _bars_from_closes([100.0] * 5)
        engine = BacktestEngine(_Silent("SPY"), _build_config())
        result = engine.run({"SPY": bars})
        assert result.trades == []
        assert result.final_equity == pytest.approx(100_000.0)

    def test_result_dates_span_bars(self) -> None:
        bars = _bars_from_closes([100.0] * 5)
        engine = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config())
        result = engine.run({"SPY": bars})
        assert result.start == date(2024, 1, 2)
        assert result.end == date(2024, 1, 6)

    def test_position_sizing_equal_weight_single_uses_full_cash(self) -> None:
        closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
        opens = [c - 1.0 for c in closes]
        bars = _bars_from_closes(closes, opens)
        engine = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config(cash=100_000.0))
        result = engine.run({"SPY": bars})
        first_snapshot = result.equity_curve[1]
        assert first_snapshot.positions == {"SPY": 1010}
        assert first_snapshot.cash == pytest.approx(10.0)


class TestBacktestEngineMultiTicker:
    def test_etf_rotation_end_to_end(self) -> None:
        from quant_trader.strategies import EtfRotationStrategy

        bars_per_ticker: dict[str, list[Bar]] = {}
        for t in ("SPY", "AGG"):
            closes = [100.0 + i * (0.5 if t == "SPY" else -0.2) for i in range(200)]
            bars_per_ticker[t] = _bars_from_closes(closes)
        engine = BacktestEngine(EtfRotationStrategy(params={"top_n": 1}), _build_config())
        result = engine.run(bars_per_ticker)
        assert result.strategy_name == "etf_rotation"
        assert result.final_equity > 0

    def test_unknown_strategy_type_raises(self) -> None:
        class _NotAStrategy:
            name = "fake"

        engine = BacktestEngine(_NotAStrategy(), _build_config())  # type: ignore[arg-type]
        with pytest.raises(BacktestConfigError, match="Unbekannter Strategy-Typ"):
            engine.run({"SPY": _bars_from_closes([100.0] * 5)})


class TestBacktestEngineLogging:
    def test_logs_backtest_start_and_complete(self) -> None:
        from structlog.testing import capture_logs

        bars = _bars_from_closes([100.0] * 5)
        engine = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config())
        with capture_logs() as logs:
            engine.run({"SPY": bars})
        events = [entry["event"] for entry in logs]
        assert "backtest.start" in events
        assert "backtest.complete" in events

    def test_logs_insufficient_cash(self) -> None:
        from structlog.testing import capture_logs

        bars = _bars_from_closes([100.0] * 5)
        engine = BacktestEngine(_BuyHoldStrategy("SPY"), _build_config(cash=0.5))
        with capture_logs() as logs:
            engine.run({"SPY": bars})
        events = [entry["event"] for entry in logs]
        assert "backtest.insufficient_cash" in events
