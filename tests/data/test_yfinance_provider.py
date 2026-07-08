"""Tests for YFinanceProvider."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from quant_trader.core.errors import ProviderError, TickerNotFoundError
from quant_trader.core.types import Granularity
from quant_trader.data.yfinance_provider import YFinanceProvider


def _make_df() -> pd.DataFrame:
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    data = {
        "Open": [100.0, 101.0, 102.0],
        "High": [101.0, 102.0, 103.0],
        "Low": [99.0, 100.0, 101.0],
        "Close": [100.5, 101.5, 102.5],
        "Adj Close": [100.5, 101.5, 102.5],
        "Volume": [1000, 1500, 2000],
    }
    return pd.DataFrame(data, index=idx)


def test_yfinance_name() -> None:
    assert YFinanceProvider().name == "yfinance"


def test_yfinance_returns_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    df = _make_df()

    def fake_download(*args: object, **kwargs: object) -> pd.DataFrame:
        return df

    monkeypatch.setattr("quant_trader.data.yfinance_provider.yf.download", fake_download)

    prov = YFinanceProvider()
    bars = prov.fetch("SPY", date(2024, 1, 2), date(2024, 1, 4), Granularity.DAILY)

    assert len(bars) == 3
    assert bars[0].open == 100.0
    assert bars[2].close == 102.5
    assert bars[1].volume == 1500


def test_yfinance_handles_multi_index_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    idx = pd.to_datetime(["2024-01-02"])
    cols = pd.MultiIndex.from_tuples(
        [("Open", "SPY"), ("High", "SPY"), ("Low", "SPY"), ("Close", "SPY"), ("Adj Close", "SPY"), ("Volume", "SPY")]
    )
    data = [(100.0, 101.0, 99.0, 100.5, 100.5, 1000)]
    df = pd.DataFrame(data, index=idx, columns=cols)

    def fake_download(*args: object, **kwargs: object) -> pd.DataFrame:
        return df

    monkeypatch.setattr("quant_trader.data.yfinance_provider.yf.download", fake_download)

    bars = YFinanceProvider().fetch("SPY", date(2024, 1, 2), date(2024, 1, 2), Granularity.DAILY)

    assert len(bars) == 1
    assert bars[0].open == 100.0
    assert bars[0].adjusted_close == 100.5


def test_yfinance_empty_dataframe_raises_ticker_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_download(*args: object, **kwargs: object) -> pd.DataFrame:
        return pd.DataFrame()

    monkeypatch.setattr("quant_trader.data.yfinance_provider.yf.download", fake_download)

    with pytest.raises(TickerNotFoundError) as exc:
        YFinanceProvider().fetch("ZZZZZ", date(2024, 1, 2), date(2024, 1, 4), Granularity.DAILY)
    assert exc.value.ticker == "ZZZZZ"


def test_yfinance_network_error_raises_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_download(*args: object, **kwargs: object) -> pd.DataFrame:
        raise ConnectionError("no internet")

    monkeypatch.setattr("quant_trader.data.yfinance_provider.yf.download", fake_download)

    with pytest.raises(ProviderError) as exc:
        YFinanceProvider().fetch("SPY", date(2024, 1, 2), date(2024, 1, 4), Granularity.DAILY)
    assert exc.value.provider == "yfinance"
    assert "no internet" in str(exc.value)