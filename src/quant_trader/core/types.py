"""Shared domain types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


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


@dataclass(frozen=True)
class Instrument:
    ticker: str
    name: str
    exchange: str
    currency: str
    instrument_type: str = ""
    country: str = ""
    sector: str = ""
    exchange_full_name: str = ""
    is_active: bool = True


@dataclass(frozen=True)
class ExchangeDescriptor:
    code: str
    name: str


@dataclass(frozen=True)
class InstrumentSnapshotMeta:
    snapshot_id: str
    built_at: datetime
    source: str
    total: int


class Granularity(StrEnum):
    DAILY = "daily"
    INTRADAY_60M = "60m"
    INTRADAY_15M = "15m"

    @property
    def path_segment(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    volume: int
