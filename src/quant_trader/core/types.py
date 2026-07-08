"""Shared domain types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


@dataclass(frozen=True)
class Preset:
    name: str
    description: str
    tickers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "tickers": list(self.tickers),
        }


class Granularity(str, Enum):
    DAILY = "daily"
    INTRADAY_60M = "60m"
    INTRADAY_15M = "15m"

    @property
    def path_segment(self) -> str:
        return self.value


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    volume: int