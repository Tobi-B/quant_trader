"""Tests for LongCapitalShortLaborStrategy."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from quant_trader.core.types import Bar
from quant_trader.strategies import (
    Action,
    LongCapitalShortLaborStrategy,
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


def _feed(
    strategy: LongCapitalShortLaborStrategy,
    series: list[tuple[datetime, dict[str, Bar]]],
    portfolio: PortfolioState = PortfolioState(),
) -> list:
    sigs: list = []
    for ts, by_ticker in series:
        sigs.extend(strategy.on_universe_bars(ts, by_ticker, portfolio))
    return sigs


def test_default_params_and_combined_universe() -> None:
    strategy = LongCapitalShortLaborStrategy()
    assert strategy.params["long_universe"] == ["QQQ", "SPY", "VNQ", "JPM"]
    assert strategy.params["short_universe"] == ["XRT", "XLI", "IYT", "JETS"]
    assert strategy.params["lookback_months"] == 6
    assert strategy.params["entry_threshold"] == 0.02
    assert strategy.params["exit_threshold"] == 0.0
    assert strategy.params["rebalance_freq"] == "monthly"
    assert strategy.params["universe"] == [
        "QQQ",
        "SPY",
        "VNQ",
        "JPM",
        "XRT",
        "XLI",
        "IYT",
        "JETS",
    ]


def test_warmup_bars_default() -> None:
    strategy = LongCapitalShortLaborStrategy()
    assert strategy.warmup_bars() == 6 * _TRADING_DAYS_PER_MONTH


def test_empty_long_universe_raises() -> None:
    with pytest.raises(StrategyError, match="long_universe"):
        LongCapitalShortLaborStrategy(params={"long_universe": []})


def test_empty_short_universe_raises() -> None:
    with pytest.raises(StrategyError, match="short_universe"):
        LongCapitalShortLaborStrategy(params={"short_universe": []})


def test_invalid_lookback_raises() -> None:
    with pytest.raises(StrategyError, match="lookback_months"):
        LongCapitalShortLaborStrategy(params={"lookback_months": 0})


def test_invalid_thresholds_raises() -> None:
    with pytest.raises(StrategyError, match="entry_threshold"):
        LongCapitalShortLaborStrategy(params={"entry_threshold": 0.01, "exit_threshold": 0.05})


def test_invalid_rebalance_freq_raises() -> None:
    with pytest.raises(StrategyError, match="nicht implementiert"):
        LongCapitalShortLaborStrategy(params={"rebalance_freq": "weekly"})


def test_no_signals_during_warmup() -> None:
    strategy = LongCapitalShortLaborStrategy(params={"lookback_months": 2})
    long_bars = _bars_for_ticker(_monthly_to_daily_closes(100.0, [0.10, 0.10]))
    short_bars = _bars_for_ticker(_monthly_to_daily_closes(100.0, [0.05, 0.05]))
    series = _align_to_same_day(
        {
            "QQQ": long_bars,
            "SPY": long_bars,
            "VNQ": long_bars,
            "JPM": long_bars,
            "XRT": short_bars,
            "XLI": short_bars,
            "IYT": short_bars,
            "JETS": short_bars,
        }
    )
    signals = _feed(strategy, series)
    assert signals == []


def test_entry_on_positive_spread() -> None:
    strategy = LongCapitalShortLaborStrategy(params={"lookback_months": 2})
    long_closes = _monthly_to_daily_closes(100.0, [0.05, 0.05, 0.10, 0.10])
    short_closes = _monthly_to_daily_closes(100.0, [0.02, 0.02, 0.03, 0.03])
    long_bars = _bars_for_ticker(long_closes)
    short_bars = _bars_for_ticker(short_closes)
    series = _align_to_same_day(
        {
            "QQQ": long_bars,
            "SPY": long_bars,
            "VNQ": long_bars,
            "JPM": long_bars,
            "XRT": short_bars,
            "XLI": short_bars,
            "IYT": short_bars,
            "JETS": short_bars,
        }
    )
    signals = _feed(strategy, series)
    buys = sorted({s.ticker for s in signals if s.action is Action.BUY})
    sells = sorted({s.ticker for s in signals if s.action is Action.SELL})
    assert buys == ["JPM", "QQQ", "SPY", "VNQ"]
    assert sells == ["IYT", "JETS", "XLI", "XRT"]
    assert all(s.reason == "lcsl_long_entry" for s in signals if s.action is Action.BUY)
    assert all(s.reason == "lcsl_short_entry" for s in signals if s.action is Action.SELL)


def test_hold_when_spread_between_thresholds() -> None:
    strategy = LongCapitalShortLaborStrategy(
        params={"lookback_months": 2, "entry_threshold": 0.10, "exit_threshold": -0.10}
    )
    long_closes = _monthly_to_daily_closes(100.0, [0.02, 0.02, 0.025, 0.025])
    short_closes = _monthly_to_daily_closes(100.0, [0.01, 0.01, 0.015, 0.015])
    long_bars = _bars_for_ticker(long_closes)
    short_bars = _bars_for_ticker(short_closes)
    series = _align_to_same_day(
        {
            "QQQ": long_bars,
            "SPY": long_bars,
            "VNQ": long_bars,
            "JPM": long_bars,
            "XRT": short_bars,
            "XLI": short_bars,
            "IYT": short_bars,
            "JETS": short_bars,
        }
    )
    signals = _feed(strategy, series)
    assert signals == []


def test_exit_when_spread_drops_below_exit_threshold() -> None:
    strategy = LongCapitalShortLaborStrategy(params={"lookback_months": 2})
    long_phase1 = _monthly_to_daily_closes(100.0, [0.10, 0.10, 0.10, 0.10])
    short_phase1 = _monthly_to_daily_closes(100.0, [0.01, 0.01, 0.01, 0.01])
    long_bars1 = _bars_for_ticker(long_phase1)
    short_bars1 = _bars_for_ticker(short_phase1)
    holdings = PortfolioState(
        positions={"QQQ": 1, "SPY": 1, "VNQ": 1, "JPM": 1, "XRT": 1, "XLI": 1, "IYT": 1, "JETS": 1}
    )
    _feed(
        strategy,
        _align_to_same_day(
            {
                "QQQ": long_bars1,
                "SPY": long_bars1,
                "VNQ": long_bars1,
                "JPM": long_bars1,
                "XRT": short_bars1,
                "XLI": short_bars1,
                "IYT": short_bars1,
                "JETS": short_bars1,
            }
        ),
        holdings,
    )

    long_phase2 = _monthly_to_daily_closes(long_phase1[-1], [-0.05, -0.05, -0.05, -0.05])
    short_phase2 = _monthly_to_daily_closes(short_phase1[-1], [0.10, 0.10, 0.10, 0.10])
    long_bars2 = _bars_for_ticker(long_phase2, day_offset_start=len(long_phase1))
    short_bars2 = _bars_for_ticker(short_phase2, day_offset_start=len(short_phase1))
    signals = _feed(
        strategy,
        _align_to_same_day(
            {
                "QQQ": long_bars2,
                "SPY": long_bars2,
                "VNQ": long_bars2,
                "JPM": long_bars2,
                "XRT": short_bars2,
                "XLI": short_bars2,
                "IYT": short_bars2,
                "JETS": short_bars2,
            }
        ),
        holdings,
    )
    buys = sorted({s.ticker for s in signals if s.action is Action.BUY})
    sells = sorted({s.ticker for s in signals if s.action is Action.SELL})
    assert buys == ["IYT", "JETS", "XLI", "XRT"]
    assert sells == ["JPM", "QQQ", "SPY", "VNQ"]
    assert all(s.reason == "lcsl_long_exit" for s in signals if s.action is Action.SELL)
    assert all(s.reason == "lcsl_short_cover" for s in signals if s.action is Action.BUY)


def test_no_signals_when_in_position_and_spread_between_thresholds() -> None:
    strategy = LongCapitalShortLaborStrategy(
        params={"lookback_months": 2, "entry_threshold": 0.05, "exit_threshold": -0.10}
    )
    long_phase1 = _monthly_to_daily_closes(100.0, [0.10, 0.10, 0.10, 0.10])
    short_phase1 = _monthly_to_daily_closes(100.0, [0.01, 0.01, 0.01, 0.01])
    long_bars1 = _bars_for_ticker(long_phase1)
    short_bars1 = _bars_for_ticker(short_phase1)
    holdings = PortfolioState(
        positions={"QQQ": 1, "SPY": 1, "VNQ": 1, "JPM": 1, "XRT": 1, "XLI": 1, "IYT": 1, "JETS": 1}
    )
    entry_signals = _feed(
        strategy,
        _align_to_same_day(
            {
                "QQQ": long_bars1,
                "SPY": long_bars1,
                "VNQ": long_bars1,
                "JPM": long_bars1,
                "XRT": short_bars1,
                "XLI": short_bars1,
                "IYT": short_bars1,
                "JETS": short_bars1,
            }
        ),
        holdings,
    )
    assert len(entry_signals) == 8

    long_phase2 = _monthly_to_daily_closes(long_phase1[-1], [0.01, 0.01, 0.01, 0.01])
    short_phase2 = _monthly_to_daily_closes(short_phase1[-1], [0.005, 0.005, 0.005, 0.005])
    long_bars2 = _bars_for_ticker(long_phase2, day_offset_start=len(long_phase1))
    short_bars2 = _bars_for_ticker(short_phase2, day_offset_start=len(short_phase1))
    hold_signals = _feed(
        strategy,
        _align_to_same_day(
            {
                "QQQ": long_bars2,
                "SPY": long_bars2,
                "VNQ": long_bars2,
                "JPM": long_bars2,
                "XRT": short_bars2,
                "XLI": short_bars2,
                "IYT": short_bars2,
                "JETS": short_bars2,
            }
        ),
        holdings,
    )
    assert hold_signals == []


def test_custom_universes_kept_in_combined_field() -> None:
    strategy = LongCapitalShortLaborStrategy(
        params={
            "long_universe": ["A", "B"],
            "short_universe": ["C", "D"],
            "lookback_months": 1,
        }
    )
    assert strategy.params["universe"] == ["A", "B", "C", "D"]
    assert strategy._long_universe == ["A", "B"]
    assert strategy._short_universe == ["C", "D"]


def test_uppercase_normalization_in_baskets() -> None:
    strategy = LongCapitalShortLaborStrategy(
        params={
            "long_universe": ["qqq", "spy"],
            "short_universe": ["xrt"],
            "lookback_months": 1,
        }
    )
    assert strategy._long_universe == ["QQQ", "SPY"]
    assert strategy._short_universe == ["XRT"]
