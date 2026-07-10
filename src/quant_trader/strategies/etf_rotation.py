"""ETF Top-N momentum rotation strategy.

Cross-sectional monthly rotation: at the first bar of each month the
strategy computes the lookback-month return for every ETF in the
universe, selects the top-N performers, emits SELL signals for holdings
that dropped out of the top-N and BUY signals for new entrants. When no
ETF has a positive lookback return the strategy liquidates all holdings
to cash (defensive branch).
"""

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

_DEFAULT_UNIVERSE: list[str] = ["SPY", "AGG", "TLT", "IEF"]


class EtfRotationStrategy(MultiTickerStrategyBase):
    name: ClassVar[str] = "etf_rotation"
    version: ClassVar[str] = "1.0.0"
    default_params: ClassVar[dict[str, Any]] = {
        "universe": list(_DEFAULT_UNIVERSE),
        "top_n": 2,
        "lookback_months": 6,
        "rebalance_freq": "monthly",
    }

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        universe = [str(t) for t in self.params["universe"]]
        top_n = int(self.params["top_n"])
        lookback_months = int(self.params["lookback_months"])
        rebalance_freq = str(self.params["rebalance_freq"])
        if not universe:
            raise StrategyError("universe darf nicht leer sein")
        if top_n < 1:
            raise StrategyError(f"top_n muss >= 1 sein (got {top_n})")
        if lookback_months < 1:
            raise StrategyError(f"lookback_months muss >= 1 sein (got {lookback_months})")
        if rebalance_freq != "monthly":
            raise StrategyError(
                f"rebalance_freq '{rebalance_freq}' nicht implementiert (nur 'monthly')"
            )
        if len(universe) < top_n:
            raise StrategyError(f"top_n ({top_n}) muss <= len(universe) ({len(universe)}) sein")
        self._universe = universe
        self._top_n = top_n
        self._lookback_months = lookback_months
        self._rebalance_freq = rebalance_freq
        self._lookback_bars = lookback_months * _TRADING_DAYS_PER_MONTH
        self._history: dict[str, deque[Bar]] = {}
        self._current_holdings: set[str] = set()
        self._last_rebalance_key: tuple[int, int] | None = None

    def warmup_bars(self) -> int:
        return self._lookback_bars

    def _append_history(self, bars_by_ticker: dict[str, Bar]) -> None:
        for ticker, bar in bars_by_ticker.items():
            history = self._history.get(ticker)
            if history is None:
                history = deque(maxlen=self._lookback_bars + 1)
                self._history[ticker] = history
            history.append(bar)

    @staticmethod
    def _rebalance_key(timestamp: datetime) -> tuple[int, int]:
        return (timestamp.year, timestamp.month)

    def _is_rebalance_day(self, timestamp: datetime) -> bool:
        return self._rebalance_key(timestamp) != self._last_rebalance_key

    def _all_etfs_warm(self, bars_by_ticker: dict[str, Bar]) -> bool:
        for ticker in bars_by_ticker:
            history = self._history.get(ticker)
            if history is None or len(history) <= self._lookback_bars:
                return False
        return True

    def _compute_returns(self, bars_by_ticker: dict[str, Bar]) -> dict[str, float]:
        returns: dict[str, float] = {}
        for ticker in bars_by_ticker:
            history = self._history.get(ticker)
            if history is None or len(history) <= self._lookback_bars:
                continue
            closes = [b.close for b in history]
            start_close = closes[-self._lookback_bars]
            if start_close <= 0:
                continue
            returns[ticker] = closes[-1] / start_close - 1.0
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
        if not self._all_etfs_warm(bars_by_ticker):
            log.debug(
                "etf_rotation.warmup_pending",
                timestamp=timestamp.isoformat(),
                lookback_bars=self._lookback_bars,
            )
            return []
        returns = self._compute_returns(bars_by_ticker)
        signals: list[Signal] = []
        positive = {t: r for t, r in returns.items() if r > 0}
        if not positive:
            for held in sorted(self._current_holdings):
                signals.append(
                    Signal(
                        timestamp=timestamp,
                        ticker=held,
                        action=Action.SELL,
                        reason="etf_rotation_defensive_cash",
                    )
                )
            self._current_holdings = set(portfolio.positions.keys())
            self._last_rebalance_key = self._rebalance_key(timestamp)
            if signals:
                log.info(
                    "etf_rotation.defensive_cash",
                    timestamp=timestamp.isoformat(),
                    liquidations=len(signals),
                )
            return signals
        ranked = sorted(positive.items(), key=lambda kv: kv[1], reverse=True)
        top_n_set = {t for t, _ in ranked[: self._top_n]}
        for held in sorted(self._current_holdings - top_n_set):
            signals.append(
                Signal(
                    timestamp=timestamp,
                    ticker=held,
                    action=Action.SELL,
                    reason="etf_rotation_dropped_from_top_n",
                )
            )
        for target in sorted(top_n_set - self._current_holdings):
            signals.append(
                Signal(
                    timestamp=timestamp,
                    ticker=target,
                    action=Action.BUY,
                    reason="etf_rotation_entered_top_n",
                )
            )
        self._current_holdings = set(portfolio.positions.keys())
        self._last_rebalance_key = self._rebalance_key(timestamp)
        if signals:
            log.info(
                "etf_rotation.rebalance",
                timestamp=timestamp.isoformat(),
                top_n=sorted(top_n_set),
                signals=len(signals),
            )
        return signals
