"""Tests for universe CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from quant_trader.core.types import ExchangeDescriptor, Instrument
from quant_trader.data.instrument_catalog import (
    InstrumentCatalogService,
    InstrumentCatalogSnapshotStore,
)
from quant_trader.universe import cli as cli_module
from quant_trader.universe.cli import main
from quant_trader.universe.dynamic_store import DynamicUniverseStore


class _FakeCatalogProvider:
    def __init__(
        self, stocks: list[Instrument] | None = None, raise_on: Exception | None = None
    ) -> None:
        self._stocks = stocks or []
        self._raise_on = raise_on

    def fetch_stock_list(self) -> list[Instrument]:
        if self._raise_on is not None:
            raise self._raise_on
        return self._stocks

    def fetch_etf_list(self) -> list[Instrument]:
        return []

    def fetch_fund_list(self) -> list[Instrument]:
        return []

    def fetch_index_list(self) -> list[Instrument]:
        return []

    def fetch_crypto_list(self) -> list[Instrument]:
        return []

    def fetch_exchanges(self) -> list[ExchangeDescriptor]:
        return []

    def fetch_sectors(self) -> list[str]:
        return []

    def fetch_countries(self) -> list[str]:
        return []

    def fetch_index_membership(self, index_id: str) -> list[str]:
        return []


@pytest.fixture
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cfg = tmp_path / "presets.yaml"
    cfg.write_text(
        "sp500:\n  description: Test\n  tickers: [AAPL, MSFT]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("UNIVERSE_PRESETS_PATH", str(cfg))
    from quant_trader.core.config import get_settings

    get_settings.cache_clear()
    return tmp_path


def test_cli_load_writes_csv(isolated_settings: Path) -> None:
    rc = main(["load", "--preset", "sp500"])

    assert rc == 0
    out = isolated_settings / "universe" / "sp500.csv"
    assert out.exists()
    assert out.read_text(encoding="utf-8").splitlines() == ["ticker", "AAPL", "MSFT"]


def test_cli_load_unknown_preset_returns_1(isolated_settings: Path) -> None:
    rc = main(["load", "--preset", "dax40"])

    assert rc == 1


def test_cli_list_returns_0(isolated_settings: Path) -> None:
    rc = main(["list"])

    assert rc == 0


@pytest.fixture
def catalog_settings(isolated_settings: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CATALOG_PATH", str(isolated_settings / "catalog" / "instruments.parquet"))
    monkeypatch.setenv("DYNAMIC_UNIVERSES_PATH", str(isolated_settings / "dynamic_universe"))
    from quant_trader.core.config import get_settings

    get_settings.cache_clear()
    return isolated_settings


def _patch_catalog_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    provider: _FakeCatalogProvider,
) -> InstrumentCatalogService:
    service = InstrumentCatalogService(
        provider,
        InstrumentCatalogSnapshotStore(tmp_path / "catalog" / "instruments.parquet"),
        DynamicUniverseStore(tmp_path / "dynamic_universe"),
    )
    monkeypatch.setattr(cli_module, "_build_catalog_service", lambda: service)
    return service


def _stock(ticker: str) -> Instrument:
    return Instrument(
        ticker=ticker,
        name=f"{ticker} Inc.",
        exchange="NASDAQ",
        currency="USD",
        instrument_type="stock",
    )


class TestCatalogCommand:
    def test_status_before_any_refresh_returns_0(self, catalog_settings: Path) -> None:
        rc = main(["catalog", "status"])
        assert rc == 0

    def test_refresh_happy_path_returns_0(
        self, catalog_settings: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_catalog_service(
            monkeypatch, catalog_settings, _FakeCatalogProvider([_stock("AAPL")])
        )

        rc = main(["catalog", "refresh"])

        assert rc == 0

    def test_refresh_unavailable_returns_1(
        self, catalog_settings: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quant_trader.core.errors import ProviderError

        _patch_catalog_service(
            monkeypatch,
            catalog_settings,
            _FakeCatalogProvider(raise_on=ProviderError("fmp", "boom")),
        )

        rc = main(["catalog", "refresh"])

        assert rc == 1

    def test_list_after_refresh_returns_0(
        self, catalog_settings: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_catalog_service(
            monkeypatch, catalog_settings, _FakeCatalogProvider([_stock("AAPL"), _stock("BRK.B")])
        )
        assert main(["catalog", "refresh"]) == 0

        rc = main(["catalog", "list", "--query", "BRK.B"])

        assert rc == 0

    def test_list_without_snapshot_returns_1(self, catalog_settings: Path) -> None:
        rc = main(["catalog", "list", "--query", "AAPL"])
        assert rc == 1


class TestUniverseDynamicCommand:
    def test_save_and_list_and_load(
        self, catalog_settings: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_catalog_service(
            monkeypatch, catalog_settings, _FakeCatalogProvider([_stock("AAPL"), _stock("MSFT")])
        )
        assert main(["catalog", "refresh"]) == 0

        rc = main(["universe", "save", "--name", "my_stocks", "--type", "stock"])
        assert rc == 0

        assert main(["universe", "list"]) == 0
        assert main(["universe", "load", "--name", "my_stocks"]) == 0

    def test_save_empty_selection_returns_1(
        self, catalog_settings: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_catalog_service(
            monkeypatch, catalog_settings, _FakeCatalogProvider([_stock("AAPL")])
        )
        assert main(["catalog", "refresh"]) == 0

        rc = main(["universe", "save", "--name", "empty", "--query", "ZZZZ"])

        assert rc == 1

    def test_save_already_exists_without_overwrite_returns_1(
        self, catalog_settings: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_catalog_service(
            monkeypatch, catalog_settings, _FakeCatalogProvider([_stock("AAPL")])
        )
        assert main(["catalog", "refresh"]) == 0
        assert main(["universe", "save", "--name", "dup"]) == 0

        rc = main(["universe", "save", "--name", "dup"])

        assert rc == 1

    def test_save_with_overwrite_succeeds(
        self, catalog_settings: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_catalog_service(
            monkeypatch, catalog_settings, _FakeCatalogProvider([_stock("AAPL")])
        )
        assert main(["catalog", "refresh"]) == 0
        assert main(["universe", "save", "--name", "dup"]) == 0

        rc = main(["universe", "save", "--name", "dup", "--overwrite"])

        assert rc == 0

    def test_load_missing_returns_1(self, catalog_settings: Path) -> None:
        rc = main(["universe", "load", "--name", "does_not_exist"])
        assert rc == 1

    def test_list_empty_returns_0(self, catalog_settings: Path) -> None:
        rc = main(["universe", "list"])
        assert rc == 0
