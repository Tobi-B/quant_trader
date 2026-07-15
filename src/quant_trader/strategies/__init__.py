"""Strategy package: types, base classes, loader, and concrete strategies."""

from __future__ import annotations

from quant_trader.strategies.base import MultiTickerStrategyBase, StrategyBase
from quant_trader.strategies.docs import StrategyDocLoader
from quant_trader.strategies.errors import (
    StrategyConfigError,
    StrategyError,
    UnknownStrategyError,
)
from quant_trader.strategies.etf_rotation import EtfRotationStrategy
from quant_trader.strategies.loader import StrategyLoader
from quant_trader.strategies.momentum import MomentumStrategy
from quant_trader.strategies.rsi_mean_reversion import RsiMeanReversionStrategy
from quant_trader.strategies.runner import SignalFormatter, SignalRunner
from quant_trader.strategies.sma_cross import SmaCrossStrategy
from quant_trader.strategies.types import Action, PortfolioState, Signal, StrategyConfig

__all__ = [
    "Action",
    "EtfRotationStrategy",
    "MomentumStrategy",
    "MultiTickerStrategyBase",
    "PortfolioState",
    "RsiMeanReversionStrategy",
    "Signal",
    "SignalFormatter",
    "SignalRunner",
    "SmaCrossStrategy",
    "StrategyBase",
    "StrategyConfig",
    "StrategyConfigError",
    "StrategyDocLoader",
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
        _default_loader.register(EtfRotationStrategy)
    return _default_loader
