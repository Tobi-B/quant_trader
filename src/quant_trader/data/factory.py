"""ProviderFactory - assembles the data provider chain from Settings."""

from __future__ import annotations

from quant_trader.core.config import Settings
from quant_trader.data.alpha_vantage import AlphaVantageProvider
from quant_trader.data.fallback import FallbackProvider
from quant_trader.data.financial_modelling_prep import FinancialModellingPrepProvider
from quant_trader.data.stockdata_provider import StockDataProvider
from quant_trader.data.yfinance_provider import YFinanceProvider


def build_chain(settings: Settings) -> FallbackProvider:
    primary = FinancialModellingPrepProvider(api_key=settings.fmp_api_key)
    fallbacks = [
        YFinanceProvider(),
        StockDataProvider(api_token=settings.stockdata_api_token),
        AlphaVantageProvider(api_key=settings.alphavantage_key),
    ]
    return FallbackProvider(primary=primary, fallbacks=fallbacks)
