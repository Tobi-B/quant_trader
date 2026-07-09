"""StrategyBase and MultiTickerStrategyBase abstract base classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar

from quant_trader.core.types import Bar
from quant_trader.strategies.types import PortfolioState, Signal


class StrategyBase(ABC):
    """Abstract base for single-ticker strategies.

    Subclasses must set the `name` ClassVar to a unique non-empty string
    (used as the registry key by `StrategyLoader`) and implement
    `warmup_bars` and `on_bar`. `default_params` is merged with the
    constructor's `params` argument (constructor values win).

    Single-ticker strategies are bound to one ticker via the `ticker`
    constructor argument; `on_bar` uses `self.ticker` to populate emitted
    `Signal.ticker` values.
    """

    name: ClassVar[str] = ""
    version: ClassVar[str] = "1.0.0"
    default_params: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        ticker: str = "",
        params: dict[str, Any] | None = None,
    ) -> None:
        self.ticker: str = ticker
        self.params: dict[str, Any] = {**self.default_params, **(params or {})}

    @abstractmethod
    def warmup_bars(self) -> int:
        """Number of bars needed before the strategy can produce signals."""

    @abstractmethod
    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
        """Process one bar and return 0+ signals."""


class MultiTickerStrategyBase(ABC):
    """Abstract base for universe-based strategies.

    Subclasses set `name` and implement `warmup_bars` and `on_universe_bars`.
    Used by strategies that need to rank or compare across multiple tickers
    at a single point in time (e.g. momentum rotation, ETF top-N).
    Signals emitted from `on_universe_bars` carry their ticker explicitly.
    """

    name: ClassVar[str] = ""
    version: ClassVar[str] = "1.0.0"
    default_params: ClassVar[dict[str, Any]] = {}

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params: dict[str, Any] = {**self.default_params, **(params or {})}

    @abstractmethod
    def warmup_bars(self) -> int:
        """Number of bars needed per ticker before the strategy can produce signals."""

    @abstractmethod
    def on_universe_bars(
        self,
        timestamp: datetime,
        bars_by_ticker: dict[str, Bar],
        portfolio: PortfolioState,
    ) -> list[Signal]:
        """Process all bars for one date across the universe and return 0+ signals."""
