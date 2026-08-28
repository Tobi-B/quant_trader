"""Tests for the key-free public catalog sources (ADR-0019).

Fixtures mirror the real file layouts byte-for-byte in structure
(delimiters, header rows, trailer lines), so a parser that only works
against a simplified shape fails here.
"""

from __future__ import annotations

from typing import cast

import pytest
import requests

from quant_trader.core.errors import ProviderError
from quant_trader.core.types import ExchangeDescriptor
from quant_trader.data.public_catalog import (
    CoinGeckoSource,
    NasdaqTraderSource,
    PublicCatalogProvider,
    XetraSource,
)

_NASDAQ_LISTED = (
    "Symbol|Security Name|Market Category|Test Issue|Financial Status|"
    "Round Lot Size|ETF|NextShares\n"
    "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\n"
    "QQQ|Invesco QQQ Trust|G|N|N|100|Y|N\n"
    "ZXZZT|NASDAQ TEST STOCK|G|Y|N|100|N|N\n"
    "File Creation Time: 0828202606:00|||||||\n"
)

_OTHER_LISTED = (
    "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|"
    "Test Issue|NASDAQ Symbol\n"
    "BRK.B|Berkshire Hathaway Inc. New Common Stock|N|BRK.B|N|40|N|BRK-B\n"
    "SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY\n"
    "ZXIET|IEX Test Company|V|ZXIET|N|100|Y|ZXIET\n"
    "File Creation Time: 0828202606:00||||||\n"
)

_XETRA_CSV = (
    "Market:;XETR\n"
    "Date Last Update:;28.08.2026\n"
    "Product Status;Instrument Status;Instrument;ISIN;Product ID;Instrument ID;"
    "WKN;Mnemonic;MIC Code;CCP eligible Code;Trading Model Type;"
    "Product Assignment Group;Product Assignment Group Description;"
    "Designated Sponsor Member ID;Designated Sponsor;Price Range Value;"
    "Price Range Percentage;Minimum Quote Size;Instrument Type;Tick Size 1\n"
    "Active;Active;SAP SE O.N.;DE0007164600;52984;2505077;000716460;SAP;XETR;Y;"
    "Continuous;DAX1;DAX;;;;2;54;CS;0.0001\n"
    "Active;Active;VOLKSWAGEN AG VZO O.N.;DE0007664039;52999;2505078;000766403;"
    "VOW3;XETR;Y;Continuous;DAX1;DAX;;;;2;54;CS;0.0001\n"
    "Active;Active;ISHARES CORE DAX;DE0005933931;53000;2505079;000593393;EXS1;"
    "XETR;Y;Continuous;EFT0;EXCHANGE TRADED FUNDS - PASSIV;;;;2;54;ETF;0.0001\n"
    "Active;Inactive;DELISTED AG;DE0009999999;53001;2505080;000999999;DEL;XETR;Y;"
    "Continuous;AST0;DEUTSCHLAND;;;;2;54;CS;0.0001\n"
)

_COINGECKO_JSON = [
    {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
    {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
]


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", payload: object = None) -> None:
        self.status_code = status_code
        self.content = text.encode("utf-8")
        self._payload = payload

    def json(self) -> object:
        return self._payload


class _RoutingSession:
    """Returns a canned response per URL substring."""

    def __init__(self, routes: dict[str, _FakeResponse]) -> None:
        self._routes = routes
        self.requested: list[str] = []

    def get(self, url: str, **kwargs: object) -> _FakeResponse:
        self.requested.append(url)
        for fragment, response in self._routes.items():
            if fragment in url:
                return response
        raise AssertionError(f"unexpected URL: {url}")


class _BrokenSession:
    def get(self, url: str, **kwargs: object) -> _FakeResponse:
        raise requests.ConnectionError("offline")


def _nasdaq_session() -> _RoutingSession:
    return _RoutingSession(
        {
            "nasdaqlisted": _FakeResponse(200, _NASDAQ_LISTED),
            "otherlisted": _FakeResponse(200, _OTHER_LISTED),
        }
    )


def _nasdaq(session: _RoutingSession | None = None) -> NasdaqTraderSource:
    return NasdaqTraderSource(
        session=cast(requests.Session, session if session is not None else _nasdaq_session())
    )


def _xetra(text: str = _XETRA_CSV) -> XetraSource:
    session = _RoutingSession({"allTradableInstruments": _FakeResponse(200, text)})
    return XetraSource(session=cast(requests.Session, session))


def _coingecko(payload: object = None) -> CoinGeckoSource:
    session = _RoutingSession(
        {
            "coins/markets": _FakeResponse(
                200, payload=_COINGECKO_JSON if payload is None else payload
            )
        }
    )
    return CoinGeckoSource(session=cast(requests.Session, session))


class TestNasdaqTraderSource:
    def test_parses_both_files(self) -> None:
        instruments = _nasdaq().fetch_all()

        tickers = {i.ticker for i in instruments}
        assert {"AAPL", "QQQ", "BRK.B", "SPY"} <= tickers

    def test_keeps_dotted_class_share_symbol(self) -> None:
        """US-P1.10 requires BRK.B verbatim; this is the only source with it."""
        instruments = _nasdaq().fetch_all()

        brk = next(i for i in instruments if i.ticker == "BRK.B")
        assert brk.exchange == "NYSE"
        assert brk.instrument_type == "stock"
        assert brk.country == "US"

    def test_drops_test_issues(self) -> None:
        tickers = {i.ticker for i in _nasdaq().fetch_all()}

        assert "ZXZZT" not in tickers
        assert "ZXIET" not in tickers

    def test_drops_trailer_line(self) -> None:
        tickers = {i.ticker for i in _nasdaq().fetch_all()}

        assert not any(t.startswith("FILE CREATION") for t in tickers)

    def test_maps_etf_flag(self) -> None:
        by_ticker = {i.ticker: i for i in _nasdaq().fetch_all()}

        assert by_ticker["QQQ"].instrument_type == "etf"
        assert by_ticker["SPY"].instrument_type == "etf"
        assert by_ticker["AAPL"].instrument_type == "stock"

    def test_maps_exchange_codes(self) -> None:
        by_ticker = {i.ticker: i for i in _nasdaq().fetch_all()}

        assert by_ticker["AAPL"].exchange == "NASDAQ"
        assert by_ticker["SPY"].exchange == "NYSE ARCA"

    def test_http_error_raises_provider_error(self) -> None:
        session = _RoutingSession({"nasdaqlisted": _FakeResponse(503)})
        source = NasdaqTraderSource(session=cast(requests.Session, session))

        with pytest.raises(ProviderError, match="HTTP 503"):
            source.fetch_all()

    def test_network_error_raises_provider_error(self) -> None:
        source = NasdaqTraderSource(session=cast(requests.Session, _BrokenSession()))

        with pytest.raises(ProviderError, match="network"):
            source.fetch_all()


class TestXetraSource:
    def test_parses_active_instruments(self) -> None:
        instruments = _xetra().fetch_all()

        assert {i.ticker for i in instruments} == {"SAP", "VOW3", "EXS1"}

    def test_skips_inactive_instruments(self) -> None:
        assert "DEL" not in {i.ticker for i in _xetra().fetch_all()}

    def test_maps_instrument_types(self) -> None:
        by_ticker = {i.ticker: i for i in _xetra().fetch_all()}

        assert by_ticker["SAP"].instrument_type == "stock"
        assert by_ticker["EXS1"].instrument_type == "etf"

    def test_derives_country_from_isin(self) -> None:
        by_ticker = {i.ticker: i for i in _xetra().fetch_all()}

        assert by_ticker["SAP"].country == "DE"

    def test_index_membership_for_dax40(self) -> None:
        assert _xetra().fetch_index_membership("dax40") == ["SAP", "VOW3"]

    def test_index_membership_unknown_index_is_empty(self) -> None:
        assert _xetra().fetch_index_membership("sp500") == []

    def test_missing_header_raises_provider_error(self) -> None:
        with pytest.raises(ProviderError, match="unexpected file layout"):
            _xetra("Market:;XETR\nno header here\n").fetch_all()


class TestCoinGeckoSource:
    def test_parses_coins(self) -> None:
        instruments = _coingecko().fetch_all()

        assert [i.ticker for i in instruments] == ["BTC", "ETH"]
        assert all(i.instrument_type == "crypto" for i in instruments)
        assert all(i.currency == "USD" for i in instruments)

    def test_http_error_raises_provider_error(self) -> None:
        session = _RoutingSession({"coins/markets": _FakeResponse(429)})
        source = CoinGeckoSource(session=cast(requests.Session, session))

        with pytest.raises(ProviderError, match="HTTP 429"):
            source.fetch_all()

    def test_invalid_payload_raises_provider_error(self) -> None:
        with pytest.raises(ProviderError, match="invalid JSON"):
            _coingecko(payload={"unexpected": "shape"}).fetch_all()

    def test_limit_is_bounded(self) -> None:
        source = CoinGeckoSource(
            session=cast(requests.Session, _RoutingSession({})), limit=10_000
        )

        assert source._limit == 250


class TestPublicCatalogProvider:
    def _provider(self) -> PublicCatalogProvider:
        return PublicCatalogProvider(
            nasdaq=_nasdaq(), xetra=_xetra(), coingecko=_coingecko()
        )

    def test_stock_list_spans_us_and_eu(self) -> None:
        tickers = {i.ticker for i in self._provider().fetch_stock_list()}

        assert {"AAPL", "BRK.B", "SAP", "VOW3"} <= tickers
        assert "QQQ" not in tickers

    def test_etf_list_includes_etn_and_etc_types(self) -> None:
        tickers = {i.ticker for i in self._provider().fetch_etf_list()}

        assert {"QQQ", "SPY", "EXS1"} <= tickers

    def test_crypto_list(self) -> None:
        assert {i.ticker for i in self._provider().fetch_crypto_list()} == {"BTC", "ETH"}

    def test_fund_list_is_empty_and_honest(self) -> None:
        assert self._provider().fetch_fund_list() == []

    def test_index_list_is_empty(self) -> None:
        assert self._provider().fetch_index_list() == []

    def test_exchanges_are_deduplicated_and_sorted(self) -> None:
        exchanges = self._provider().fetch_exchanges()

        assert all(isinstance(e, ExchangeDescriptor) for e in exchanges)
        codes = [e.code for e in exchanges]
        assert codes == sorted(codes)
        assert "XETRA" in codes

    def test_countries(self) -> None:
        assert set(self._provider().fetch_countries()) == {"US", "DE"}

    def test_index_membership_delegates_to_xetra(self) -> None:
        assert self._provider().fetch_index_membership("dax40") == ["SAP", "VOW3"]

    def test_index_membership_unknown_raises(self) -> None:
        with pytest.raises(ProviderError, match="unbekannter Index"):
            self._provider().fetch_index_membership("sp500")

    def test_one_failing_source_does_not_break_the_others(self) -> None:
        provider = PublicCatalogProvider(
            nasdaq=NasdaqTraderSource(session=cast(requests.Session, _BrokenSession())),
            xetra=_xetra(),
            coingecko=_coingecko(),
        )

        tickers = {i.ticker for i in provider.fetch_stock_list()}

        assert "SAP" in tickers
        assert "AAPL" not in tickers

    def test_sources_are_downloaded_once_per_refresh(self) -> None:
        """Each fetch_*_list call must not re-download every source."""
        session = _nasdaq_session()
        provider = PublicCatalogProvider(
            nasdaq=_nasdaq(session), xetra=_xetra(), coingecko=_coingecko()
        )

        provider.fetch_stock_list()
        provider.fetch_etf_list()
        provider.fetch_crypto_list()

        assert len(session.requested) == 2  # nasdaqlisted + otherlisted, once

    def test_invalidate_forces_a_fresh_download(self) -> None:
        session = _nasdaq_session()
        provider = PublicCatalogProvider(
            nasdaq=_nasdaq(session), xetra=_xetra(), coingecko=_coingecko()
        )

        provider.fetch_stock_list()
        provider.invalidate()
        provider.fetch_stock_list()

        assert len(session.requested) == 4

    def test_all_sources_failing_raises(self) -> None:
        broken = cast(requests.Session, _BrokenSession())
        provider = PublicCatalogProvider(
            nasdaq=NasdaqTraderSource(session=broken),
            xetra=XetraSource(session=broken),
            coingecko=CoinGeckoSource(session=broken),
        )

        with pytest.raises(ProviderError, match="all catalog sources failed"):
            provider.fetch_stock_list()
