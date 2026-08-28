"""Tests for FinancialModellingPrepProvider."""

from __future__ import annotations

from datetime import date, datetime
from typing import cast

import pytest
import requests

from quant_trader.core.errors import ProviderError, RateLimitedError, TickerNotFoundError
from quant_trader.core.types import Bar, ExchangeDescriptor, Granularity
from quant_trader.data.financial_modelling_prep import FinancialModellingPrepProvider


class _FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        return self._payload


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.last_url: str | None = None
        self.last_timeout: int | None = None

    def get(self, url: str, timeout: int = 0) -> _FakeResponse:
        self.last_url = url
        self.last_timeout = timeout
        return self._response


class _BrokenSession:
    def get(self, url: str, timeout: int = 0) -> _FakeResponse:
        raise requests.ConnectionError("offline")


def _daily_row(day: str, value: float) -> dict[str, object]:
    return {
        "symbol": "SPY",
        "date": day,
        "open": value,
        "high": value + 1.0,
        "low": value - 1.0,
        "close": value + 0.5,
        "volume": 1000,
    }


def _intraday_row(timestamp: str, value: float) -> dict[str, object]:
    row = _daily_row(timestamp, value)
    return row


def _provider(response: _FakeResponse) -> tuple[FinancialModellingPrepProvider, _FakeSession]:
    session = _FakeSession(response)
    provider = FinancialModellingPrepProvider(
        api_key="test-key", session=cast(requests.Session, session)
    )
    return provider, session


def test_fetch_daily_happy_path() -> None:
    payload = [_daily_row("2024-01-03", 101.0), _daily_row("2024-01-02", 100.0)]
    provider, session = _provider(_FakeResponse(200, payload))

    bars = provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert isinstance(bars, list)
    assert all(isinstance(bar, Bar) for bar in bars)
    assert [bar.timestamp for bar in bars] == [
        datetime(2024, 1, 2, 16),
        datetime(2024, 1, 3, 16),
    ]
    assert session.last_url == (
        "https://financialmodelingprep.com/stable/historical-price-eod/full"
        "?symbol=SPY&from=2024-01-02&to=2024-01-03&apikey=test-key"
    )
    assert session.last_timeout == 30


def test_fetch_60m_happy_path() -> None:
    payload = [_intraday_row("2024-01-02 10:00:00", 100.0)]
    provider, session = _provider(_FakeResponse(200, payload))

    bars = provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 2), Granularity.INTRADAY_60M)

    assert len(bars) == 1
    assert bars[0].timestamp == datetime(2024, 1, 2, 10)
    assert session.last_url is not None
    assert "/historical-chart/1hour?" in session.last_url
    assert "symbol=SPY" in session.last_url


def test_fetch_15m_happy_path() -> None:
    payload = [_intraday_row("2024-01-02 10:15:00", 100.0)]
    provider, session = _provider(_FakeResponse(200, payload))

    bars = provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 2), Granularity.INTRADAY_15M)

    assert len(bars) == 1
    assert bars[0].timestamp == datetime(2024, 1, 2, 10, 15)
    assert session.last_url is not None
    assert "/historical-chart/15min?" in session.last_url
    assert "symbol=SPY" in session.last_url


def test_empty_historical_raises_ticker_not_found() -> None:
    provider, _ = _provider(_FakeResponse(200, []))

    with pytest.raises(TickerNotFoundError) as exc:
        provider.fetch("ZZZZ", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert exc.value.ticker == "ZZZZ"


def test_invalid_api_key_raises_provider_error() -> None:
    provider, _ = _provider(_FakeResponse(200, {"Error Message": "Invalid API KEY."}))

    with pytest.raises(ProviderError) as exc:
        provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert "Invalid API KEY." in str(exc.value)


def test_rate_limit_raises_rate_limited() -> None:
    provider, _ = _provider(_FakeResponse(200, {"Error Message": "Limit Reach ..."}))

    with pytest.raises(RateLimitedError) as exc:
        provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert "Limit Reach" in str(exc.value)


def test_http_429_raises_rate_limited() -> None:
    provider, _ = _provider(_FakeResponse(429, {}))

    with pytest.raises(RateLimitedError) as exc:
        provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert "HTTP 429" in str(exc.value)


def test_http_500_raises_provider_error() -> None:
    provider, _ = _provider(_FakeResponse(500, {}))

    with pytest.raises(ProviderError) as exc:
        provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert "HTTP 500" in str(exc.value)


def test_network_error_raises_provider_error() -> None:
    provider = FinancialModellingPrepProvider(
        api_key="test-key",
        session=cast(requests.Session, _BrokenSession()),
    )

    with pytest.raises(ProviderError) as exc:
        provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert "network: offline" in str(exc.value)


def test_no_api_key_raises_provider_error() -> None:
    provider = FinancialModellingPrepProvider(api_key="")

    with pytest.raises(ProviderError) as exc:
        provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert "FINANCIAL_MODELLING_PREP_KEY not set" in str(exc.value)


def test_date_filter_excludes_out_of_range() -> None:
    payload = [
        _daily_row("2024-01-01", 99.0),
        _daily_row("2024-01-02", 100.0),
        _daily_row("2024-01-04", 103.0),
    ]
    provider, _ = _provider(_FakeResponse(200, payload))

    bars = provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 3), Granularity.DAILY)

    assert [bar.timestamp.date() for bar in bars] == [date(2024, 1, 2)]


def test_adjclose_falls_back_to_close_when_missing() -> None:
    payload = [_daily_row("2024-01-02", 100.0)]
    provider, _ = _provider(_FakeResponse(200, payload))

    bars = provider.fetch("SPY", date(2024, 1, 2), date(2024, 1, 2), Granularity.DAILY)

    assert bars[0].adjusted_close == bars[0].close == 100.5


def test_fetch_stock_list_parses_instruments() -> None:
    payload = [
        {"symbol": "AAPL", "name": "Apple Inc.", "exchangeShortName": "NASDAQ"},
        {"symbol": "BRK.B", "name": "Berkshire Hathaway Inc.", "exchangeShortName": "NYSE"},
    ]
    provider, session = _provider(_FakeResponse(200, payload))

    instruments = provider.fetch_stock_list()

    assert [i.ticker for i in instruments] == ["AAPL", "BRK.B"]
    assert all(i.instrument_type == "stock" for i in instruments)
    assert session.last_url == (
        "https://financialmodelingprep.com/stable/stock-list?apikey=test-key"
    )


def test_fetch_etf_list_parses_instruments() -> None:
    payload = [{"symbol": "SPY", "name": "SPDR S&P 500", "exchangeShortName": "NYSEARCA"}]
    provider, session = _provider(_FakeResponse(200, payload))

    instruments = provider.fetch_etf_list()

    assert instruments[0].instrument_type == "etf"
    assert "/stable/etf-list?" in (session.last_url or "")


def test_fetch_index_list_parses_instruments() -> None:
    payload = [{"symbol": "^GSPC", "name": "S&P 500"}]
    provider, _ = _provider(_FakeResponse(200, payload))

    instruments = provider.fetch_index_list()

    assert instruments[0].instrument_type == "index"
    assert instruments[0].exchange == "Unbekannt"


def test_fetch_crypto_list_parses_instruments() -> None:
    payload = [{"symbol": "BTCUSD", "name": "Bitcoin USD", "currency": "USD"}]
    provider, _ = _provider(_FakeResponse(200, payload))

    instruments = provider.fetch_crypto_list()

    assert instruments[0].instrument_type == "crypto"
    assert instruments[0].currency == "USD"


def test_fetch_fund_list_returns_empty_on_http_403() -> None:
    provider, _ = _provider(_FakeResponse(403, {}))

    instruments = provider.fetch_fund_list()

    assert instruments == []


def test_fetch_fund_list_returns_empty_on_empty_payload() -> None:
    provider, _ = _provider(_FakeResponse(200, []))

    assert provider.fetch_fund_list() == []


def test_fetch_fund_list_parses_when_available() -> None:
    payload = [{"symbol": "VTSAX", "name": "Vanguard Total Stock"}]
    provider, _ = _provider(_FakeResponse(200, payload))

    instruments = provider.fetch_fund_list()

    assert instruments[0].instrument_type == "fund"


def test_fetch_exchanges_parses_descriptors() -> None:
    payload = [{"exchange": "NASDAQ", "name": "NASDAQ Global Market"}]
    provider, _ = _provider(_FakeResponse(200, payload))

    exchanges = provider.fetch_exchanges()

    assert exchanges == [ExchangeDescriptor(code="NASDAQ", name="NASDAQ Global Market")]


def test_fetch_sectors_returns_sorted_unique_strings() -> None:
    payload = [{"sector": "Technology"}, {"sector": "Energy"}, {"sector": "Technology"}]
    provider, _ = _provider(_FakeResponse(200, payload))

    assert provider.fetch_sectors() == ["Energy", "Technology"]


def test_fetch_countries_returns_sorted_unique_strings() -> None:
    payload = ["US", "DE", "US"]
    provider, _ = _provider(_FakeResponse(200, payload))

    assert provider.fetch_countries() == ["DE", "US"]


def test_fetch_index_membership_returns_uppercased_tickers() -> None:
    payload = [{"symbol": "aapl"}, {"symbol": "MSFT"}]
    provider, session = _provider(_FakeResponse(200, payload))

    tickers = provider.fetch_index_membership("sp500")

    assert tickers == ["AAPL", "MSFT"]
    assert "/stable/sp500-constituent?" in (session.last_url or "")


def test_fetch_index_membership_unknown_index_raises_provider_error() -> None:
    provider, _ = _provider(_FakeResponse(200, []))

    with pytest.raises(ProviderError):
        provider.fetch_index_membership("dax40")


def test_catalog_methods_rate_limited() -> None:
    provider, _ = _provider(_FakeResponse(429, {}))

    with pytest.raises(RateLimitedError):
        provider.fetch_stock_list()


def test_catalog_methods_no_api_key_raises_provider_error() -> None:
    provider = FinancialModellingPrepProvider(api_key="")

    with pytest.raises(ProviderError):
        provider.fetch_stock_list()


def test_catalog_methods_network_error_raises_provider_error() -> None:
    provider = FinancialModellingPrepProvider(
        api_key="test-key",
        session=cast(requests.Session, _BrokenSession()),
    )

    with pytest.raises(ProviderError):
        provider.fetch_etf_list()
