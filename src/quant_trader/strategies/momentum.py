"""Momentum 12-1 cross-sectional strategy."""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, ClassVar

from quant_trader.core.logging import get_logger
from quant_trader.core.types import Bar
from quant_trader.strategies.base import MultiTickerStrategyBase
from quant_trader.strategies.errors import StrategyError
from quant_trader.strategies.types import Action, PortfolioState, Signal

log = get_logger(__name__)

_TRADING_DAYS_PER_MONTH = 21


class MomentumStrategy(MultiTickerStrategyBase):
    name: ClassVar[str] = "momentum"
    version: ClassVar[str] = "1.0.0"
    default_params: ClassVar[dict[str, Any]] = {
        "lookback_months": 12,
        "skip_recent_months": 1,
        "top_n": 10,
        "rebalance_freq": "monthly",
    }

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        lookback = int(self.params["lookback_months"])
        skip = int(self.params["skip_recent_months"])
        top_n = int(self.params["top_n"])
        freq = str(self.params["rebalance_freq"])
        if lookback < 1:
            raise StrategyError(f"lookback_months muss >= 1 sein (got {lookback})")
        if skip < 0:
            raise StrategyError(f"skip_recent_months muss >= 0 sein (got {skip})")
        if lookback <= skip:
            raise StrategyError(
                f"lookback_months ({lookback}) muss > skip_recent_months ({skip}) sein"
            )
        if top_n < 1:
            raise StrategyError(f"top_n muss >= 1 sein (got {top_n})")
        if freq != "monthly":
            raise StrategyError(f"rebalance_freq '{freq}' nicht implementiert (nur 'monthly')")
        self._max_history = (lookback + skip + 1) * _TRADING_DAYS_PER_MONTH
        self._lookback = lookback
        self._skip = skip
        self._top_n = top_n
        self._freq = freq
        self._history: dict[str, deque[Bar]] = {}
        self._current_holdings: set[str] = set()
        self._last_rebalance_key: tuple[int, int] | None = None

    def warmup_bars(self) -> int:
        return (self._lookback + self._skip) * _TRADING_DAYS_PER_MONTH

    def _append_history(self, bars_by_ticker: dict[str, Bar]) -> None:
        for ticker, bar in bars_by_ticker.items():
            history = self._history.get(ticker)
            if history is None:
                history = deque(maxlen=self._max_history)
                self._history[ticker] = history
            history.append(bar)

    def _rebalance_key(self, timestamp: datetime) -> tuple[int, int]:
        return (timestamp.year, timestamp.month)

    def _is_rebalance_day(self, timestamp: datetime) -> bool:
        return self._last_rebalance_key != self._rebalance_key(timestamp)

    def _compute_returns(self, bars_by_ticker: dict[str, Bar]) -> dict[str, float]:
        skip_idx = self._skip * _TRADING_DAYS_PER_MONTH
        lookback_idx = (self._skip + self._lookback) * _TRADING_DAYS_PER_MONTH
        returns: dict[str, float] = {}
        for ticker in bars_by_ticker:
            history = self._history.get(ticker)
            if history is None or len(history) <= lookback_idx:
                continue
            closes = [b.close for b in history]
            end_close = closes[-skip_idx] if skip_idx > 0 else closes[-1]
            start_close = closes[-lookback_idx]
            if start_close <= 0:
                continue
            returns[ticker] = end_close / start_close - 1.0
        return returns

    def on_universe_bars(
        self,
        timestamp: datetime,
        bars_by_ticker: dict[str, Bar],
        portfolio: PortfolioState,
    ) -> list[Signal]:
        self._append_history(bars_by_ticker)
        if not self._is_rebalance_day(timestamp):
            return []
        lookback_idx = (self._skip + self._lookback) * _TRADING_DAYS_PER_MONTH
        insufficient = [
            t
            for t in bars_by_ticker
            if t not in self._history or len(self._history[t]) <= lookback_idx
        ]
        if insufficient:
            log.debug(
                "momentum.warmup_pending",
                timestamp=timestamp.isoformat(),
                insufficient=insufficient,
            )
            return []
        returns = self._compute_returns(bars_by_ticker)
        if not returns:
            return []
        ranked = sorted(returns.items(), key=lambda kv: kv[1], reverse=True)
        top_n_tickers = {t for t, _ in ranked[: self._top_n]}
        signals: list[Signal] = []
        for held in self._current_holdings - top_n_tickers:
            signals.append(
                Signal(
                    timestamp=timestamp,
                    ticker=held,
                    action=Action.SELL,
                    reason="momentum_dropped_from_top_n",
                )
            )
        for target in top_n_tickers - self._current_holdings:
            signals.append(
                Signal(
                    timestamp=timestamp,
                    ticker=target,
                    action=Action.BUY,
                    reason="momentum_entered_top_n",
                )
            )
        self._current_holdings = set(portfolio.positions.keys())
        self._last_rebalance_key = self._rebalance_key(timestamp)
        if signals:
            log.info(
                "momentum.rebalance",
                timestamp=timestamp.isoformat(),
                top_n=sorted(top_n_tickers),
                signals=len(signals),
            )
        return signals
