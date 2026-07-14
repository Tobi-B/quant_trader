"""Fill simulator: turns a Signal into a Fill according to FillMode."""

from __future__ import annotations

from quant_trader.backtest.types import Fill, FillMode, PendingFill
from quant_trader.core.types import Bar
from quant_trader.strategies.types import Signal


class FillSimulator:
    """Creates PendingFills and resolves them to Fills.

    - `NEXT_OPEN`: the fill is executed on the *next* bar at its `open` price.
    - `SAME_CLOSE`: the fill is executed on the *signal* bar at its `close`
      price (no look-ahead; the strategy saw the close before emitting the
      signal, so we can fill at the same close).
    - `slippage_pct`: applied to the reference price at `resolve()` time.
      BUY: `price = raw * (1 + slippage_pct / 100)`,
      SELL: `price = raw * (1 - slippage_pct / 100)`. Default `0.0`
      preserves the original (unslipped) price.
    """

    def __init__(self, mode: FillMode, slippage_pct: float = 0.0) -> None:
        self._mode = mode
        self._slippage_pct = slippage_pct

    def schedule(self, signal: Signal, bars: list[Bar], current_index: int) -> PendingFill:
        if self._mode is FillMode.SAME_CLOSE:
            execute_bar = bars[current_index]
        else:
            next_idx = current_index + 1
            if next_idx >= len(bars):
                raise ValueError(f"NEXT_OPEN fill requested for {signal.ticker} at end of bar list")
            execute_bar = bars[next_idx]
        return PendingFill(signal=signal, execute_on=execute_bar)

    def resolve(self, pending: PendingFill) -> Fill:
        raw_price = (
            pending.execute_on.open
            if self._mode is FillMode.NEXT_OPEN
            else pending.execute_on.close
        )
        action = pending.signal.action
        if action.value == "BUY":
            price = float(raw_price) * (1.0 + self._slippage_pct / 100.0)
        else:
            price = float(raw_price) * (1.0 - self._slippage_pct / 100.0)
        return Fill(
            ticker=pending.signal.ticker,
            timestamp=pending.execute_on.timestamp,
            price=price,
            qty=0,
            action=str(action.value),
        )
