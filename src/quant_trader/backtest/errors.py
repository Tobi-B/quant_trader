"""Backtest module error hierarchy."""

from __future__ import annotations

from pathlib import Path


class BacktestError(Exception):
    """Base for all backtest-module errors."""


class BacktestConfigError(BacktestError):
    """Backtest configuration is invalid (empty bars, missing sizer, etc.)."""


class InvalidParamsError(BacktestError):
    """Backtest-Orchestrator received invalid parameters (start > end, etc.)."""


class UnknownStrategyError(BacktestError):
    """Strategy name is not in the loader registry."""

    def __init__(self, name: str, available: list[str]) -> None:
        available_str = ", ".join(available) if available else "(keine)"
        super().__init__(f"Unbekannte Strategie: '{name}'. Verfuegbar: {available_str}")
        self.name = name
        self.available = list(available)


class CacheMissingError(BacktestError):
    """Required Parquet cache file is missing for a ticker."""

    def __init__(self, ticker: str, path: Path) -> None:
        super().__init__(
            f"Kein Cache fuer {ticker} unter {path}. "
            f"Erst `python -m quant_trader.data {ticker}` aufrufen."
        )
        self.ticker = ticker
        self.path = path
