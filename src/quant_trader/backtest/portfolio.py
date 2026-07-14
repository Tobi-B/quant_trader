"""Portfolio: immutable snapshot of cash + per-ticker share counts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Portfolio:
    cash: float = 0.0
    positions: dict[str, int] = field(default_factory=dict)

    def with_cash(self, delta: float) -> Portfolio:
        return Portfolio(cash=self.cash + delta, positions=dict(self.positions))

    def with_position(self, ticker: str, delta_shares: int) -> Portfolio:
        if delta_shares == 0:
            return self
        positions = dict(self.positions)
        current = positions.get(ticker, 0)
        new_qty = current + delta_shares
        if new_qty == 0:
            positions.pop(ticker, None)
        else:
            positions[ticker] = new_qty
        return Portfolio(cash=self.cash, positions=positions)

    def equity(self, prices: dict[str, float]) -> float:
        position_value = sum(
            qty * prices.get(ticker, 0.0) for ticker, qty in self.positions.items()
        )
        return self.cash + position_value

    def n_open_positions(self) -> int:
        return sum(1 for qty in self.positions.values() if qty > 0)

    def position_qty(self, ticker: str) -> int:
        return self.positions.get(ticker, 0)
