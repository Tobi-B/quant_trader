"""Tests for EtfRotationStrategy."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from quant_trader.core.types import Bar
from quant_trader.strategies import (
    Action,
    EtfRotationStrategy,
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
    strategy: EtfRotationStrategy,
    series: list[tuple[datetime, dict[str, Bar]]],
    portfolio: PortfolioState = PortfolioState(),
) -> list:
    sigs: list = []
    for ts, by_ticker in series:
        sigs.extend(strategy.on_universe_bars(ts, by_ticker, portfolio))
    return sigs


def test_warmup_bars_default() -> None:
    strategy = EtfRotationStrategy(
        params={"universe": ["SPY", "AGG"], "top_n": 1, "lookback_months": 6}
    )
    assert strategy.warmup_bars() == 6 * 21


def test_warmup_bars_with_custom_lookback() -> None:
    strategy = EtfRotationStrategy(
        params={"universe": ["A", "B"], "top_n": 1, "lookback_months": 3}
    )
    assert strategy.warmup_bars() == 3 * 21


def test_default_params() -> None:
    strategy = EtfRotationStrategy()
    assert strategy.params == {
        "universe": ["SPY", "AGG", "TLT", "IEF"],
        "top_n": 2,
        "lookback_months": 6,
        "rebalance_freq": "monthly",
    }


def test_invalid_top_n_raises() -> None:
    with pytest.raises(StrategyError, match="top_n muss >= 1"):
        EtfRotationStrategy(params={"universe": ["A", "B"], "top_n": 0})


def test_invalid_lookback_months_raises() -> None:
    with pytest.raises(StrategyError, match="lookback_months muss >= 1"):
        EtfRotationStrategy(params={"universe": ["A", "B"], "top_n": 1, "lookback_months": 0})


def test_invalid_rebalance_freq_raises() -> None:
    with pytest.raises(StrategyError, match="nicht implementiert"):
        EtfRotationStrategy(
            params={
                "universe": ["A", "B"],
                "top_n": 1,
                "rebalance_freq": "weekly",
            }
        )


def test_universe_too_small_for_top_n_raises() -> None:
    with pytest.raises(StrategyError, match="<="):
        EtfRotationStrategy(params={"universe": ["A"], "top_n": 2})


def test_empty_universe_raises() -> None:
    with pytest.raises(StrategyError, match="darf nicht leer"):
        EtfRotationStrategy(params={"universe": [], "top_n": 1})


def test_no_signals_during_warmup() -> None:
    strategy = EtfRotationStrategy(
        params={
            "universe": ["A", "B"],
            "top_n": 2,
            "lookback_months": 2,
        }
    )
    closes_a = _monthly_to_daily_closes(100.0, [0.05, 0.05])
    closes_b = _monthly_to_daily_closes(100.0, [-0.05, -0.05])
    bars_a = _bars_for_ticker(closes_a)
    bars_b = _bars_for_ticker(closes_b)
    series = _align_to_same_day({"A": bars_a, "B": bars_b})
    signals = _feed(strategy, series)
    assert signals == []


def test_buy_top_n_at_first_rebalance_after_warmup() -> None:
    strategy = EtfRotationStrategy(
        params={
            "universe": ["A", "B", "C"],
            "top_n": 2,
            "lookback_months": 1,
        }
    )
    closes_a = _monthly_to_daily_closes(100.0, [0.05, 0.05])
    closes_b = _monthly_to_daily_closes(100.0, [0.10, 0.10])
    closes_c = _monthly_to_daily_closes(100.0, [-0.10, -0.10])
    bars_a = _bars_for_ticker(closes_a)
    bars_b = _bars_for_ticker(closes_b)
    bars_c = _bars_for_ticker(closes_c)
    series = _align_to_same_day({"A": bars_a, "B": bars_b, "C": bars_c})
    signals = _feed(strategy, series)
    targets = {s.ticker for s in signals if s.action is Action.BUY}
    assert targets == {"A", "B"}


def test_sell_when_holder_drops_out_of_top_n() -> None:
    strategy = EtfRotationStrategy(
        params={
            "universe": ["A", "B"],
            "top_n": 1,
            "lookback_months": 2,
        }
    )
    a_phase1 = _monthly_to_daily_closes(100.0, [0.05, 0.05, 0.05, 0.05])
    b_phase1 = _monthly_to_daily_closes(100.0, [0.10, 0.10, 0.10, 0.10])
    bars_a1 = _bars_for_ticker(a_phase1)
    bars_b1 = _bars_for_ticker(b_phase1)
    holdings = PortfolioState(positions={"A": 1, "B": 1})
    _feed(strategy, _align_to_same_day({"A": bars_a1, "B": bars_b1}), holdings)

    a_phase2 = _monthly_to_daily_closes(a_phase1[-1], [-0.20, -0.20, -0.20, -0.20])
    b_phase2 = _monthly_to_daily_closes(b_phase1[-1], [0.20, 0.20, 0.20, 0.20])
    bars_a2 = _bars_for_ticker(a_phase2, day_offset_start=len(a_phase1))
    bars_b2 = _bars_for_ticker(b_phase2, day_offset_start=len(b_phase1))
    series2 = _align_to_same_day({"A": bars_a2, "B": bars_b2})
    signals = _feed(strategy, series2, holdings)
    sell_targets = {s.ticker for s in signals if s.action is Action.SELL}
    assert "A" in sell_targets


def test_defensive_cash_when_no_positive_return() -> None:
    strategy = EtfRotationStrategy(
        params={
            "universe": ["A", "B"],
            "top_n": 2,
            "lookback_months": 2,
        }
    )
    a_phase1 = _monthly_to_daily_closes(100.0, [0.05, 0.05, 0.05, 0.05])
    b_phase1 = _monthly_to_daily_closes(100.0, [0.10, 0.10, 0.10, 0.10])
    bars_a1 = _bars_for_ticker(a_phase1)
    bars_b1 = _bars_for_ticker(b_phase1)
    holdings = PortfolioState(positions={"A": 1, "B": 1})
    _feed(strategy, _align_to_same_day({"A": bars_a1, "B": bars_b1}), holdings)

    a_phase2 = _monthly_to_daily_closes(a_phase1[-1], [-0.10, -0.10, -0.10, -0.10])
    b_phase2 = _monthly_to_daily_closes(b_phase1[-1], [-0.10, -0.10, -0.10, -0.10])
    bars_a2 = _bars_for_ticker(a_phase2, day_offset_start=len(a_phase1))
    bars_b2 = _bars_for_ticker(b_phase2, day_offset_start=len(b_phase1))
    series2 = _align_to_same_day({"A": bars_a2, "B": bars_b2})
    signals = _feed(strategy, series2, holdings)
    sell_targets = {s.ticker for s in signals if s.action is Action.SELL}
    assert "A" in sell_targets
    assert "B" in sell_targets
    buy_targets = {s.ticker for s in signals if s.action is Action.BUY}
    assert buy_targets == set()


def test_no_signals_on_same_rebalance_month() -> None:
    strategy = EtfRotationStrategy(
        params={
            "universe": ["A", "B"],
            "top_n": 2,
            "lookback_months": 1,
        }
    )
    closes_a = _monthly_to_daily_closes(100.0, [0.05, 0.05])
    closes_b = _monthly_to_daily_closes(100.0, [0.10, 0.10])
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


def test_rebalance_event_is_logged() -> None:
    from structlog.testing import capture_logs

    strategy = EtfRotationStrategy(
        params={
            "universe": ["A", "B"],
            "top_n": 2,
            "lookback_months": 1,
        }
    )
    closes_a = _monthly_to_daily_closes(100.0, [0.05, 0.05])
    closes_b = _monthly_to_daily_closes(100.0, [0.10, 0.10])
    bars_a = _bars_for_ticker(closes_a)
    bars_b = _bars_for_ticker(closes_b)
    series = _align_to_same_day({"A": bars_a, "B": bars_b})

    with capture_logs() as captured:
        _feed(strategy, series)

    events = [e["event"] for e in captured]
    assert "etf_rotation.rebalance" in events


def test_strategy_loaded_via_loader() -> None:
    from pathlib import Path

    from quant_trader.strategies import StrategyLoader
    from quant_trader.strategies.etf_rotation import EtfRotationStrategy

    cfg = Path("config/strategies.yaml")
    loader = StrategyLoader(cfg)
    loader.register(EtfRotationStrategy)
    strategy = loader.load("etf_rotation")
    assert isinstance(strategy, EtfRotationStrategy)
    assert strategy.params["top_n"] == 2
    assert strategy.params["lookback_months"] == 6
