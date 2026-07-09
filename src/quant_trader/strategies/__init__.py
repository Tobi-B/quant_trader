"""Strategy package: types, base classes, loader, and concrete strategies."""

from __future__ import annotations

from quant_trader.strategies.base import MultiTickerStrategyBase, StrategyBase
from quant_trader.strategies.errors import (
    StrategyConfigError,
    StrategyError,
    UnknownStrategyError,
)
from quant_trader.strategies.loader import StrategyLoader
from quant_trader.strategies.momentum import MomentumStrategy
from quant_trader.strategies.rsi_mean_reversion import RsiMeanReversionStrategy
from quant_trader.strategies.sma_cross import SmaCrossStrategy
from quant_trader.strategies.types import Action, PortfolioState, Signal, StrategyConfig

__all__ = [
    "Action",
    "MomentumStrategy",
    "MultiTickerStrategyBase",
    "PortfolioState",
    "RsiMeanReversionStrategy",
    "Signal",
    "SmaCrossStrategy",
    "StrategyBase",
    "StrategyConfig",
    "StrategyConfigError",
    "StrategyError",
    "StrategyLoader",
    "UnknownStrategyError",
]

loader = StrategyLoader
_default_loader: StrategyLoader | None = None


def default_loader() -> StrategyLoader:
    global _default_loader
    if _default_loader is None:
        from quant_trader.core.config import get_settings

        _default_loader = StrategyLoader(get_settings().strategies_config_path)
        _default_loader.register(SmaCrossStrategy)
        _default_loader.register(MomentumStrategy)
        _default_loader.register(RsiMeanReversionStrategy)
    return _default_loader
