"""Tests for MomentumStrategy."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from quant_trader.core.types import Bar
from quant_trader.strategies import (
    Action,
    MomentumStrategy,
    PortfolioState,
    StrategyError,
)

_TRADING_DAYS_PER_MONTH = 21


def _bar(close: float, day_offset: int) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, 2, 16, 0) + timedelta(days=day_offset),
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        adjusted_close=close,
        volume=1000,
    )


def _monthly_to_daily_closes(start: float, monthly_returns: list[float]) -> list[float]:
    monthly_closes = [start]
    for r in monthly_returns:
        monthly_closes.append(monthly_closes[-1] * (1 + r))
    daily: list[float] = []
    for i in range(len(monthly_closes) - 1):
        begin = monthly_closes[i]
        end = monthly_closes[i + 1]
        for d in range(_TRADING_DAYS_PER_MONTH):
            t = d / _TRADING_DAYS_PER_MONTH
            daily.append(begin * (1 - t) + end * t)
    return daily


def _bars_for_ticker(daily_closes: list[float], day_offset_start: int = 0) -> list[Bar]:
    return [_bar(close=c, day_offset=day_offset_start + i) for i, c in enumerate(daily_closes)]


def _align_to_same_day(
    bars_by_ticker: dict[str, list[Bar]],
) -> list[tuple[datetime, dict[str, Bar]]]:
    all_dates = sorted({b.timestamp for bars in bars_by_ticker.values() for b in bars})
    out: list[tuple[datetime, dict[str, Bar]]] = []
    latest_per_ticker: dict[str, Bar] = {}
    for ts in all_dates:
        for ticker, bars in bars_by_ticker.items():
            for b in bars:
                if b.timestamp == ts:
                    latest_per_ticker[ticker] = b
                    break
        out.append((ts, dict(latest_per_ticker)))
    return out


def _feed(strategy: MomentumStrategy, series: list[tuple[datetime, dict[str, Bar]]]) -> list:
    sigs: list = []
    for ts, by_ticker in series:
        sigs.extend(strategy.on_universe_bars(ts, by_ticker, PortfolioState()))
    return sigs


def test_warmup_bars_uses_lookback_and_skip() -> None:
    strategy = MomentumStrategy(params={"lookback_months": 6, "skip_recent_months": 1, "top_n": 2})
    assert strategy.warmup_bars() == 7 * 21


def test_default_params() -> None:
    strategy = MomentumStrategy()
    assert strategy.params == {
        "lookback_months": 12,
        "skip_recent_months": 1,
        "top_n": 10,
        "rebalance_freq": "monthly",
    }
    assert strategy.warmup_bars() == 13 * 21


def test_invalid_lookback_le_skip_raises() -> None:
    with pytest.raises(StrategyError, match="muss > skip_recent_months"):
        MomentumStrategy(params={"lookback_months": 1, "skip_recent_months": 1})


def test_invalid_top_n_raises() -> None:
    with pytest.raises(StrategyError, match="top_n muss >= 1"):
        MomentumStrategy(params={"top_n": 0})


def test_invalid_rebalance_freq_raises() -> None:
    with pytest.raises(StrategyError, match="nicht implementiert"):
        MomentumStrategy(params={"rebalance_freq": "weekly"})


def test_invalid_lookback_too_small_raises() -> None:
    with pytest.raises(StrategyError, match="lookback_months muss >= 1"):
        MomentumStrategy(params={"lookback_months": 0})


def test_no_signals_during_warmup() -> None:
    strategy = MomentumStrategy(params={"lookback_months": 2, "skip_recent_months": 1, "top_n": 2})
    closes_a = _monthly_to_daily_closes(100.0, [0.05] * 2)
    closes_b = _monthly_to_daily_closes(100.0, [-0.05] * 2)
    bars_a = _bars_for_ticker(closes_a)
    bars_b = _bars_for_ticker(closes_b)
    series = _align_to_same_day({"A": bars_a, "B": bars_b})
    signals = _feed(strategy, series)
    assert signals == []


def test_buy_for_top_n_at_first_rebalance() -> None:
    strategy = MomentumStrategy(params={"lookback_months": 2, "skip_recent_months": 1, "top_n": 2})
    closes_a = _monthly_to_daily_closes(100.0, [0.05, 0.05, 0.05, 0.05])
    closes_b = _monthly_to_daily_closes(100.0, [0.10, 0.10, 0.10, 0.10])
    closes_c = _monthly_to_daily_closes(100.0, [-0.10, -0.10, -0.10, -0.10])
    bars_a = _bars_for_ticker(closes_a)
    bars_b = _bars_for_ticker(closes_b)
    bars_c = _bars_for_ticker(closes_c)
    series = _align_to_same_day({"A": bars_a, "B": bars_b, "C": bars_c})
    signals = _feed(strategy, series)

    buy_targets = {s.ticker for s in signals if s.action is Action.BUY}
    assert "B" in buy_targets
    assert "A" in buy_targets
    assert "C" not in buy_targets


def test_sell_when_holder_drops_out_of_top_n() -> None:
    strategy = MomentumStrategy(params={"lookback_months": 2, "skip_recent_months": 1, "top_n": 1})
    a_phase1 = _monthly_to_daily_closes(100.0, [0.05, 0.05, 0.05, 0.05])
    b_phase1 = _monthly_to_daily_closes(100.0, [0.10, 0.10, 0.10, 0.10])
    bars_a1 = _bars_for_ticker(a_phase1)
    bars_b1 = _bars_for_ticker(b_phase1)
    _feed(strategy, _align_to_same_day({"A": bars_a1, "B": bars_b1}))

    a_phase2 = _monthly_to_daily_closes(a_phase1[-1], [-0.20, -0.20, -0.20, -0.20])
    b_phase2 = _monthly_to_daily_closes(b_phase1[-1], [0.20, 0.20, 0.20, 0.20])
    bars_a2 = _bars_for_ticker(a_phase2, day_offset_start=len(a_phase1))
    bars_b2 = _bars_for_ticker(b_phase2, day_offset_start=len(b_phase1))
    series2 = _align_to_same_day({"A": bars_a2, "B": bars_b2})
    holdings = PortfolioState(positions={"A": 1})
    signals: list = []
    for ts, by_ticker in series2:
        signals.extend(strategy.on_universe_bars(ts, by_ticker, holdings))
    sell_targets = {s.ticker for s in signals if s.action is Action.SELL}
    assert "A" in sell_targets


def test_no_signals_on_same_rebalance_month() -> None:
    strategy = MomentumStrategy(params={"lookback_months": 2, "skip_recent_months": 1, "top_n": 2})
    closes_a = _monthly_to_daily_closes(100.0, [0.05, 0.05, 0.05, 0.05])
    closes_b = _monthly_to_daily_closes(100.0, [0.10, 0.10, 0.10, 0.10])
    bars_a = _bars_for_ticker(closes_a)
    bars_b = _bars_for_ticker(closes_b)
    for ts, by_ticker in _align_to_same_day({"A": bars_a, "B": bars_b}):
        strategy.on_universe_bars(ts, by_ticker, PortfolioState())
    same_month_ts = bars_a[-1].timestamp
    extra_signals = strategy.on_universe_bars(
        same_month_ts,
        {"A": bars_a[-1], "B": bars_b[-1]},
        PortfolioState(),
    )
    assert extra_signals == []


def test_logs_rebalance_event_on_signals() -> None:
    from structlog.testing import capture_logs

    strategy = MomentumStrategy(params={"lookback_months": 2, "skip_recent_months": 1, "top_n": 2})
    closes_a = _monthly_to_daily_closes(100.0, [0.05, 0.05, 0.05, 0.05])
    closes_b = _monthly_to_daily_closes(100.0, [0.10, 0.10, 0.10, 0.10])
    bars_a = _bars_for_ticker(closes_a)
    bars_b = _bars_for_ticker(closes_b)
    series = _align_to_same_day({"A": bars_a, "B": bars_b})

    with capture_logs() as captured:
        _feed(strategy, series)

    events = [e["event"] for e in captured]
    assert "momentum.rebalance" in events


def test_strategy_loaded_via_loader() -> None:
    from pathlib import Path

    from quant_trader.strategies import StrategyLoader
    from quant_trader.strategies.momentum import MomentumStrategy
    from quant_trader.strategies.sma_cross import SmaCrossStrategy

    cfg = Path("config/strategies.yaml")
    loader = StrategyLoader(cfg)
    loader.register(SmaCrossStrategy)
    loader.register(MomentumStrategy)
    sma = loader.load("sma_cross", ticker="SPY")
    mom = loader.load("momentum")
    assert isinstance(sma, SmaCrossStrategy)
    assert isinstance(mom, MomentumStrategy)
    assert sma.ticker == "SPY"
    assert sma.params["fast"] == 20
    assert sma.params["slow"] == 50
    assert mom.params["top_n"] == 10
