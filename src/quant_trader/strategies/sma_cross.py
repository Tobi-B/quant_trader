"""SMA-Crossover trend strategy."""

from __future__ import annotations

from collections import deque
from typing import Any, ClassVar

from quant_trader.core.types import Bar
from quant_trader.strategies.base import StrategyBase
from quant_trader.strategies.errors import StrategyError
from quant_trader.strategies.types import Action, PortfolioState, Signal


class SmaCrossStrategy(StrategyBase):
    name: ClassVar[str] = "sma_cross"
    version: ClassVar[str] = "1.0.0"
    default_params: ClassVar[dict[str, Any]] = {"fast": 20, "slow": 50}

    def __init__(
        self,
        ticker: str = "",
        params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(ticker=ticker, params=params)
        fast = int(self.params["fast"])
        slow = int(self.params["slow"])
        if fast < 2 or slow < 2:
            raise StrategyError(f"fast und slow muessen >= 2 sein (got fast={fast}, slow={slow})")
        if fast >= slow:
            raise StrategyError(f"fast ({fast}) muss < slow ({slow}) sein")
        self._window: deque[float] = deque(maxlen=slow)
        self._prev_fast_sma: float | None = None
        self._prev_slow_sma: float | None = None

    def warmup_bars(self) -> int:
        return int(self.params["slow"])

    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
        self._window.append(bar.close)
        slow = int(self.params["slow"])
        if len(self._window) < slow:
            return []
        fast = int(self.params["fast"])
        closes = list(self._window)
        fast_sma = sum(closes[-fast:]) / fast
        slow_sma = sum(closes[-slow:]) / slow
        signals: list[Signal] = []
        if self._prev_fast_sma is not None and self._prev_slow_sma is not None:
            prev_up = self._prev_fast_sma <= self._prev_slow_sma
            now_up = fast_sma > slow_sma
            prev_down = self._prev_fast_sma >= self._prev_slow_sma
            now_down = fast_sma < slow_sma
            if prev_up and now_up:
                signals.append(
                    Signal(
                        timestamp=bar.timestamp,
                        ticker=self.ticker,
                        action=Action.BUY,
                        reason="sma_cross_up",
                    )
                )
            elif prev_down and now_down:
                signals.append(
                    Signal(
                        timestamp=bar.timestamp,
                        ticker=self.ticker,
                        action=Action.SELL,
                        reason="sma_cross_down",
                    )
                )
        self._prev_fast_sma = fast_sma
        self._prev_slow_sma = slow_sma
        return signals
