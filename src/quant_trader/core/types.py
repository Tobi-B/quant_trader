"""Shared domain types."""

from __future__ import annotations

from dataclasses import dataclass


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