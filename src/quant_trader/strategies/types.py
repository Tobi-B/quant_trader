"""Strategy domain types: Action enum, Signal, PortfolioState, StrategyConfig."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Action(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Signal:
    timestamp: datetime
    ticker: str
    action: Action
    reason: str = ""


@dataclass(frozen=True)
class PortfolioState:
    cash: float = 0.0
    positions: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyConfig:
    strategy_name: str
    params: dict[str, Any] = field(default_factory=dict)
