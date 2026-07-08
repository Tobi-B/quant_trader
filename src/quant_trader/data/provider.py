"""DataProvider Protocol - the contract every provider implements."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from quant_trader.core.types import Bar, Granularity


class DataProvider(Protocol):
    def fetch(
        self,
        ticker: str,
        start: date,
        end: date,
        granularity: Granularity,
    ) -> list[Bar]: ...