"""Position sizer: defines how to size a BUY into integer shares given available cash."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SizingResult:
    qty: int
    allocated_cash: float
    skipped: bool


class PositionSizer(Protocol):
    """Strategy for sizing a BUY into integer shares.

    Implementations decide how many whole shares to buy given the current
    price, the available cash, and the number of currently-open positions
    (so an Equal-Weight sizer can pre-allocate the per-position share).
    """

    def allocate(
        self,
        price: float,
        available_cash: float,
        n_open_positions: int,
    ) -> SizingResult: ...


class EqualWeightSizer:
    """Allocates `available_cash / (n_open_positions + 1)` to a single BUY.

    - `n_open_positions` reflects the number of positions that are already
      open *before* this BUY. The sizer treats the new BUY as one of
      `(n_open_positions + 1)` equal-weight slots.
    - Shares are integer (whole shares only); the remainder stays in cash.
    - If `available_cash <= 0` the BUY is skipped and a `SizingResult`
      with `skipped=True` and `qty=0` is returned.
    - The per-position budget is computed defensively with `max(1, ...)`
      so that a single existing position does not collapse the budget to
      50% when opening a new one.
    """

    def allocate(
        self,
        price: float,
        available_cash: float,
        n_open_positions: int,
    ) -> SizingResult:
        if available_cash <= 0 or price <= 0:
            return SizingResult(qty=0, allocated_cash=0.0, skipped=True)
        slots = max(1, n_open_positions + 1)
        per_position_budget = available_cash / slots
        qty = int(per_position_budget // price)
        if qty <= 0:
            return SizingResult(qty=0, allocated_cash=0.0, skipped=True)
        allocated = qty * price
        return SizingResult(qty=qty, allocated_cash=allocated, skipped=False)
