"""RSI Mean-Reversion strategy (simple-average variant)."""

from __future__ import annotations

from collections import deque
from typing import Any, ClassVar

from quant_trader.core.types import Bar
from quant_trader.strategies.base import StrategyBase
from quant_trader.strategies.errors import StrategyError
from quant_trader.strategies.types import Action, PortfolioState, Signal


class RsiMeanReversionStrategy(StrategyBase):
    name: ClassVar[str] = "rsi_mean_reversion"
    version: ClassVar[str] = "1.0.0"
    default_params: ClassVar[dict[str, Any]] = {
        "period": 14,
        "oversold": 30.0,
        "overbought": 70.0,
    }

    def __init__(
        self,
        ticker: str = "",
        params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(ticker=ticker, params=params)
        period = int(self.params["period"])
        oversold = float(self.params["oversold"])
        overbought = float(self.params["overbought"])
        if period < 1:
            raise StrategyError(f"period muss >= 1 sein (got {period})")
        if not (0.0 < oversold < overbought < 100.0):
            raise StrategyError(
                f"oversold ({oversold}) und overbought ({overbought}) "
                f"muessen in (0, 100) sein mit oversold < overbought"
            )
        self._period = period
        self._oversold = oversold
        self._overbought = overbought
        self._window: deque[float] = deque(maxlen=period + 1)
        self._prev_rsi: float | None = None

    def warmup_bars(self) -> int:
        return self._period + 1

    def _compute_rsi(self) -> float:
        closes = list(self._window)
        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [c if c > 0.0 else 0.0 for c in changes]
        losses = [-c if c < 0.0 else 0.0 for c in changes]
        avg_gain = sum(gains) / self._period
        avg_loss = sum(losses) / self._period
        if avg_loss == 0.0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + rs)

    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
        self._window.append(bar.close)
        if len(self._window) < self._period + 1:
            return []
        rsi = self._compute_rsi()
        signals: list[Signal] = []
        if self._prev_rsi is not None:
            if self._prev_rsi >= self._oversold and rsi < self._oversold:
                signals.append(
                    Signal(
                        timestamp=bar.timestamp,
                        ticker=self.ticker,
                        action=Action.BUY,
                        reason="rsi_oversold_cross",
                    )
                )
            elif self._prev_rsi <= self._overbought and rsi > self._overbought:
                signals.append(
                    Signal(
                        timestamp=bar.timestamp,
                        ticker=self.ticker,
                        action=Action.SELL,
                        reason="rsi_overbought_cross",
                    )
                )
        self._prev_rsi = rsi
        return signals
