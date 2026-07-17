"""Long Capital / Short Labor: paired long/short across two baskets.

Long basket holds capital-allocation proxies (broad market, tech, banks,
REITs). Short basket holds labor-intensive sectors (retail, industrials,
transport, airlines). On each monthly rebalance the strategy computes
the 6-month return per ticker, averages within each basket, and trades
the spread:

- spread = long_avg_return - short_avg_return
- spread > entry_threshold  and not in_position -> enter
- spread < exit_threshold   and in_position     -> exit
- otherwise                                          -> hold
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

_DEFAULT_LONG_UNIVERSE: list[str] = ["QQQ", "SPY", "VNQ", "JPM"]
_DEFAULT_SHORT_UNIVERSE: list[str] = ["XRT", "XLI", "IYT", "JETS"]


class LongCapitalShortLaborStrategy(MultiTickerStrategyBase):
    name: ClassVar[str] = "long_capital_short_labor"
    version: ClassVar[str] = "1.0.0"
    default_params: ClassVar[dict[str, Any]] = {
        "long_universe": list(_DEFAULT_LONG_UNIVERSE),
        "short_universe": list(_DEFAULT_SHORT_UNIVERSE),
        "lookback_months": 6,
        "entry_threshold": 0.02,
        "exit_threshold": 0.0,
        "rebalance_freq": "monthly",
    }

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        long_universe = [str(t).upper() for t in self.params["long_universe"]]
        short_universe = [str(t).upper() for t in self.params["short_universe"]]
        lookback_months = int(self.params["lookback_months"])
        entry_threshold = float(self.params["entry_threshold"])
        exit_threshold = float(self.params["exit_threshold"])
        rebalance_freq = str(self.params["rebalance_freq"])

        if not long_universe:
            raise StrategyError("long_universe darf nicht leer sein")
        if not short_universe:
            raise StrategyError("short_universe darf nicht leer sein")
        if lookback_months < 1:
            raise StrategyError(f"lookback_months muss >= 1 sein (got {lookback_months})")
        if entry_threshold <= exit_threshold:
            raise StrategyError(
                f"entry_threshold ({entry_threshold}) muss > exit_threshold ({exit_threshold}) sein"
            )
        if rebalance_freq != "monthly":
            raise StrategyError(
                f"rebalance_freq '{rebalance_freq}' nicht implementiert (nur 'monthly')"
            )

        self._long_universe = long_universe
        self._short_universe = short_universe
        self._all_universe = list(long_universe) + list(short_universe)
        self._lookback_months = lookback_months
        self._entry_threshold = entry_threshold
        self._exit_threshold = exit_threshold
        self._lookback_bars = lookback_months * _TRADING_DAYS_PER_MONTH
        self._history: dict[str, deque[Bar]] = {}
        self._last_rebalance_key: tuple[int, int] | None = None
        self._in_position = False

        self.params["universe"] = list(self._all_universe)

    def warmup_bars(self) -> int:
        return self._lookback_bars

    def _append_history(self, bars_by_ticker: dict[str, Bar]) -> None:
        for ticker in self._all_universe:
            bar = bars_by_ticker.get(ticker)
            if bar is None:
                continue
            history = self._history.get(ticker)
            if history is None:
                history = deque(maxlen=self._lookback_bars + 1)
                self._history[ticker] = history
            history.append(bar)

    def _rebalance_key(self, timestamp: datetime) -> tuple[int, int]:
        return (timestamp.year, timestamp.month)

    def _is_rebalance_day(self, timestamp: datetime) -> bool:
        return self._last_rebalance_key != self._rebalance_key(timestamp)

    def _all_warm(self) -> bool:
        for ticker in self._all_universe:
            history = self._history.get(ticker)
            if history is None or len(history) <= self._lookback_bars:
                return False
        return True

    def _basket_return(self, universe: list[str]) -> float | None:
        closes: list[float] = []
        for ticker in universe:
            history = self._history.get(ticker)
            if history is None or len(history) <= self._lookback_bars:
                return None
            closes.append(history[-1].close)
            closes.append(history[-self._lookback_bars - 1].close)
        if not closes or len(closes) % 2 != 0:
            return None
        per_ticker_returns: list[float] = []
        for i in range(0, len(closes), 2):
            end_close = closes[i]
            start_close = closes[i + 1]
            if start_close <= 0:
                return None
            per_ticker_returns.append(end_close / start_close - 1.0)
        return sum(per_ticker_returns) / len(per_ticker_returns)

    def _emit_entry(self, timestamp: datetime) -> list[Signal]:
        signals: list[Signal] = []
        for ticker in self._long_universe:
            signals.append(
                Signal(
                    timestamp=timestamp,
                    ticker=ticker,
                    action=Action.BUY,
                    reason="lcsl_long_entry",
                )
            )
        for ticker in self._short_universe:
            signals.append(
                Signal(
                    timestamp=timestamp,
                    ticker=ticker,
                    action=Action.SELL,
                    reason="lcsl_short_entry",
                )
            )
        return signals

    def _emit_exit(self, timestamp: datetime) -> list[Signal]:
        signals: list[Signal] = []
        for ticker in self._long_universe:
            signals.append(
                Signal(
                    timestamp=timestamp,
                    ticker=ticker,
                    action=Action.SELL,
                    reason="lcsl_long_exit",
                )
            )
        for ticker in self._short_universe:
            signals.append(
                Signal(
                    timestamp=timestamp,
                    ticker=ticker,
                    action=Action.BUY,
                    reason="lcsl_short_cover",
                )
            )
        return signals

    def on_universe_bars(
        self,
        timestamp: datetime,
        bars_by_ticker: dict[str, Bar],
        portfolio: PortfolioState,
    ) -> list[Signal]:
        self._append_history(bars_by_ticker)
        if not self._is_rebalance_day(timestamp):
            return []
        insufficient = [
            ticker
            for ticker in self._all_universe
            if ticker not in self._history or len(self._history[ticker]) <= self._lookback_bars
        ]
        if insufficient or not self._all_warm():
            log.debug(
                "long_capital_short_labor.warmup_pending",
                timestamp=timestamp.isoformat(),
                insufficient=insufficient,
            )
            return []

        long_avg = self._basket_return(self._long_universe)
        short_avg = self._basket_return(self._short_universe)
        if long_avg is None or short_avg is None:
            return []

        spread = long_avg - short_avg
        signals: list[Signal] = []
        if not self._in_position and spread > self._entry_threshold:
            signals = self._emit_entry(timestamp)
            self._in_position = True
            action = "enter"
        elif self._in_position and spread < self._exit_threshold:
            signals = self._emit_exit(timestamp)
            self._in_position = False
            action = "exit"
        else:
            action = "hold"

        self._last_rebalance_key = self._rebalance_key(timestamp)
        log.info(
            "long_capital_short_labor.rebalance",
            timestamp=timestamp.isoformat(),
            spread=round(spread, 6),
            long_avg=round(long_avg, 6),
            short_avg=round(short_avg, 6),
            in_position=self._in_position,
            action=action,
            signals=len(signals),
        )
        return signals
