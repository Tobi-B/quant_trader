"""Tests for the provider factory."""

from __future__ import annotations

from quant_trader.core.config import Settings
from quant_trader.data.alpha_vantage import AlphaVantageProvider
from quant_trader.data.factory import build_chain
from quant_trader.data.financial_modelling_prep import FinancialModellingPrepProvider
from quant_trader.data.stockdata_provider import StockDataProvider
from quant_trader.data.yfinance_provider import YFinanceProvider


def test_build_chain_with_all_keys() -> None:
    settings = Settings(
        fmp_api_key="fmp-key",
        alphavantage_key="av-key",
        stockdata_api_token="stockdata-token",
    )

    chain = build_chain(settings)

    assert [provider.name for provider in chain._chain] == [
        "fmp",
        "yfinance",
        "stockdata",
        "alphavantage",
    ]
    assert isinstance(chain._chain[0], FinancialModellingPrepProvider)
    assert isinstance(chain._chain[1], YFinanceProvider)
    assert isinstance(chain._chain[2], StockDataProvider)
    assert isinstance(chain._chain[3], AlphaVantageProvider)


def test_build_chain_with_empty_fmp_key() -> None:
    chain = build_chain(Settings(fmp_api_key=""))

    assert isinstance(chain._chain[0], FinancialModellingPrepProvider)
    assert chain._chain[0]._api_key == ""


def test_build_chain_chain_length() -> None:
    chain = build_chain(Settings())

    assert len(chain._chain) == 4
