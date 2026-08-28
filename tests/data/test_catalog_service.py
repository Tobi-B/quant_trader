"""Tests for InstrumentCatalogService."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from quant_trader.core.errors import (
    CatalogRefreshError,
    CatalogUnavailableError,
    EmptyUniverseSelectionError,
    ProviderError,
    RateLimitedError,
)
from quant_trader.core.types import ExchangeDescriptor, Instrument
from quant_trader.data.instrument_catalog import InstrumentCatalogService, InstrumentCatalogSnapshotStore
from quant_trader.universe.dynamic_store import DynamicUniverseStore


class _FakeCatalogProvider:
    def __init__(
        self,
        *,
        stocks: list[Instrument] | None = None,
        etfs: list[Instrument] | None = None,
        funds: list[Instrument] | None = None,
        indices: list[Instrument] | None = None,
        crypto: list[Instrument] | None = None,
        sp500_members: list[str] | None = None,
        raise_on: str | None = None,
        exc: Exception | None = None,
    ) -> None:
        self._stocks = stocks or []
        self._etfs = etfs or []
        self._funds = funds or []
        self._indices = indices or []
        self._crypto = crypto or []
        self._sp500_members = sp500_members or []
        self._raise_on = raise_on
        self._exc = exc or ProviderError("fmp", "boom")

    def _maybe_raise(self, name: str) -> None:
        if self._raise_on == name:
            raise self._exc

    def fetch_stock_list(self) -> list[Instrument]:
        self._maybe_raise("stock_list")
        return self._stocks

    def fetch_etf_list(self) -> list[Instrument]:
        self._maybe_raise("etf_list")
        return self._etfs

    def fetch_fund_list(self) -> list[Instrument]:
        self._maybe_raise("fund_list")
        return self._funds

    def fetch_index_list(self) -> list[Instrument]:
        self._maybe_raise("index_list")
        return self._indices

    def fetch_crypto_list(self) -> list[Instrument]:
        self._maybe_raise("crypto_list")
        return self._crypto

    def fetch_exchanges(self) -> list[ExchangeDescriptor]:
        return [ExchangeDescriptor(code="NASDAQ", name="NASDAQ")]

    def fetch_sectors(self) -> list[str]:
        return ["Technology"]

    def fetch_countries(self) -> list[str]:
        return ["US"]

    def fetch_index_membership(self, index_id: str) -> list[str]:
        return self._sp500_members


def _instrument(ticker: str, *, itype: str, country: str = "", sector: str = "") -> Instrument:
    return Instrument(
        ticker=ticker,
        name=f"{ticker} Inc.",
        exchange="NASDAQ",
        currency="USD",
        instrument_type=itype,
        country=country,
        sector=sector,
    )


def _service(
    tmp_path: Path,
    provider: _FakeCatalogProvider,
    *,
    refresh_interval: timedelta = timedelta(hours=24),
) -> InstrumentCatalogService:
    store = InstrumentCatalogSnapshotStore(tmp_path / "catalog" / "instruments.parquet")
    dynamic_store = DynamicUniverseStore(tmp_path / "universe")
    return InstrumentCatalogService(
        provider, store, dynamic_store, refresh_interval=refresh_interval
    )


def test_refresh_builds_snapshot_and_dedupes(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(
        stocks=[_instrument("AAPL", itype="stock"), _instrument("BRK.B", itype="stock")],
        etfs=[_instrument("SPY", itype="etf")],
    )
    service = _service(tmp_path, provider)

    result = service.refresh()

    assert result.total == 3
    assert result.added == 3
    assert result.removed == 0
    assert result.used_fallback is False


def test_refresh_is_idempotent_within_max_age(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(stocks=[_instrument("AAPL", itype="stock")])
    service = _service(tmp_path, provider)
    service.refresh()

    result = service.refresh()

    assert result.total == 1
    assert result.added == 0
    assert result.unchanged == 1


def test_refresh_force_bypasses_freshness(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(stocks=[_instrument("AAPL", itype="stock")])
    service = _service(tmp_path, provider)
    service.refresh()

    result = service.refresh(force=True)

    assert result.used_fallback is False
    assert result.total == 1


def test_refresh_falls_back_to_existing_snapshot_on_rate_limit(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(stocks=[_instrument("AAPL", itype="stock")])
    service = _service(tmp_path, provider, refresh_interval=timedelta(seconds=0))
    service.refresh()

    provider._raise_on = "stock_list"
    provider._exc = RateLimitedError("fmp", "Limit Reach")

    result = service.refresh(force=True)

    assert result.used_fallback is True
    assert result.total == 1


def test_refresh_raises_unavailable_without_snapshot(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(raise_on="stock_list")
    service = _service(tmp_path, provider)

    with pytest.raises(CatalogUnavailableError):
        service.refresh()


def test_refresh_raises_catalog_refresh_error_for_empty_result(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider()
    service = _service(tmp_path, provider)

    with pytest.raises(CatalogRefreshError):
        service.refresh()


def test_search_finds_brk_b_by_exact_ticker(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(
        stocks=[_instrument("AAPL", itype="stock"), _instrument("BRK.B", itype="stock")]
    )
    service = _service(tmp_path, provider)
    service.refresh()

    results = service.search("BRK.B")

    assert [r.ticker for r in results] == ["BRK.B"]


def test_search_filters_by_instrument_type_and_country(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(
        stocks=[_instrument("AAPL", itype="stock", country="US")],
        etfs=[_instrument("SPY", itype="etf", country="US")],
    )
    service = _service(tmp_path, provider)
    service.refresh()

    results = service.search("", instrument_type="etf", country="US")

    assert [r.ticker for r in results] == ["SPY"]


def test_search_bounds_limit(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(
        stocks=[_instrument(f"T{i}", itype="stock") for i in range(10)]
    )
    service = _service(tmp_path, provider)
    service.refresh()

    results = service.search("T", limit=3)

    assert len(results) == 3


def test_search_without_snapshot_raises_unavailable(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider()
    service = _service(tmp_path, provider)

    with pytest.raises(CatalogUnavailableError):
        service.search("AAPL")


def test_snapshot_status_reports_total_and_freshness(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(stocks=[_instrument("AAPL", itype="stock")])
    service = _service(tmp_path, provider)
    service.refresh()

    status = service.snapshot_status()

    assert status.total == 1
    assert status.needs_refresh is False
    assert status.snapshot_id is not None


def test_build_dynamic_universe_from_filters(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(
        stocks=[_instrument("AAPL", itype="stock", country="US")],
        etfs=[_instrument("SPY", itype="etf", country="US")],
    )
    service = _service(tmp_path, provider)
    service.refresh()

    universe = service.build_dynamic_universe(
        "us_all", filters={"country": "US"}, description="Alles aus den USA"
    )

    assert universe.tickers == ("AAPL", "SPY")
    assert universe.filter_description == "Alles aus den USA"


def test_build_dynamic_universe_empty_selection_raises(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(stocks=[_instrument("AAPL", itype="stock", country="US")])
    service = _service(tmp_path, provider)
    service.refresh()

    with pytest.raises(EmptyUniverseSelectionError):
        service.build_dynamic_universe("empty", filters={"country": "DE"})


def test_build_standard_universe_etfs(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(
        stocks=[_instrument("AAPL", itype="stock")],
        etfs=[_instrument("SPY", itype="etf"), _instrument("QQQ", itype="etf")],
    )
    service = _service(tmp_path, provider)
    service.refresh()

    universe = service.build_standard_universe("etfs")

    assert universe.tickers == ("QQQ", "SPY")


def test_build_standard_universe_sp500_intersects_membership(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(
        stocks=[_instrument("AAPL", itype="stock"), _instrument("MSFT", itype="stock")],
        sp500_members=["AAPL", "TSLA"],
    )
    service = _service(tmp_path, provider)
    service.refresh()

    universe = service.build_standard_universe("sp500")

    assert universe.tickers == ("AAPL",)


def test_build_standard_universe_unknown_name_raises(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(stocks=[_instrument("AAPL", itype="stock")])
    service = _service(tmp_path, provider)
    service.refresh()

    with pytest.raises(ValueError):
        service.build_standard_universe("dax40")


def test_list_filter_options_derived_from_snapshot(tmp_path: Path) -> None:
    provider = _FakeCatalogProvider(
        stocks=[_instrument("AAPL", itype="stock", country="US", sector="Technology")],
        etfs=[_instrument("SPY", itype="etf", country="US")],
    )
    service = _service(tmp_path, provider)
    service.refresh()

    options = service.list_filter_options()

    assert options.instrument_types == ("etf", "stock")
    assert options.countries == ("US",)
    assert options.sectors == ("Technology",)
    assert "sp500" in options.indices
