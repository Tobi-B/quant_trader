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
    """

    def __init__(self, mode: FillMode) -> None:
        self._mode = mode

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
        price = (
            pending.execute_on.open
            if self._mode is FillMode.NEXT_OPEN
            else pending.execute_on.close
        )
        return Fill(
            ticker=pending.signal.ticker,
            timestamp=pending.execute_on.timestamp,
            price=float(price),
            qty=0,
            action=str(pending.signal.action.value),
        )
