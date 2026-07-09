"""Strategy module error hierarchy."""

from __future__ import annotations


class StrategyError(Exception):
    """Base for all strategy-module errors."""


class StrategyConfigError(StrategyError):
    """Strategy config file is missing, malformed, or has a missing section."""


class UnknownStrategyError(StrategyError):
    """Strategy name is not in the loader registry."""

    def __init__(self, name: str, available: list[str]) -> None:
        available_str = ", ".join(available) if available else "(keine)"
        super().__init__(f"Unbekannte Strategie: '{name}'. Verfuegbar: {available_str}")
        self.name = name
        self.available = available
