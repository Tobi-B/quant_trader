"""ProviderFactory - assembles the data provider chain from Settings."""

from __future__ import annotations

from quant_trader.core.config import Settings
from quant_trader.data.alpha_vantage import AlphaVantageProvider
from quant_trader.data.fallback import FallbackProvider
from quant_trader.data.yfinance_provider import YFinanceProvider


def build_chain(settings: Settings) -> FallbackProvider:
    primary = AlphaVantageProvider(api_key=settings.alphavantage_key)
    fallbacks = [YFinanceProvider()]
    return FallbackProvider(primary=primary, fallbacks=fallbacks)