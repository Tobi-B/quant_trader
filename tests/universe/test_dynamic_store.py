"""Tests for DynamicUniverseStore."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from quant_trader.universe.dynamic_store import (
    DynamicUniverse,
    DynamicUniverseStore,
    UniverseAlreadyExistsError,
)


def _make_universe(name: str, tickers: tuple[str, ...] = ("AAPL", "MSFT")) -> DynamicUniverse:
    return DynamicUniverse(
        name=name,
        built_from_snapshot="2026-07-19T18:53:00+00:00-3f2a",
        created_at=datetime(2026, 7, 19, 18, 53, tzinfo=UTC),
        filter_description="ETFs in den USA",
        filters={"instrument_type": "etf", "country": "US"},
        tickers=tickers,
    )


def test_path_for(tmp_path: Path) -> None:
    store = DynamicUniverseStore(tmp_path)
    assert store.path_for("us_tech_etfs") == tmp_path / "us_tech_etfs.json"


def test_exists_false_initially(tmp_path: Path) -> None:
    store = DynamicUniverseStore(tmp_path)
    assert store.exists("us_tech_etfs") is False


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    store = DynamicUniverseStore(tmp_path / "deep" / "nested")
    universe = _make_universe("us_tech_etfs")

    path = store.save(universe)

    assert path.exists()
    assert path.parent.is_dir()


def test_save_without_overwrite_refuses_existing(tmp_path: Path) -> None:
    store = DynamicUniverseStore(tmp_path)
    store.save(_make_universe("us_tech_etfs"))

    with pytest.raises(UniverseAlreadyExistsError) as exc:
        store.save(_make_universe("us_tech_etfs"))
    assert exc.value.name == "us_tech_etfs"


def test_save_with_overwrite_replaces_existing(tmp_path: Path) -> None:
    store = DynamicUniverseStore(tmp_path)
    store.save(_make_universe("us_tech_etfs", tickers=("AAPL",)))

    store.save(_make_universe("us_tech_etfs", tickers=("AAPL", "MSFT")), overwrite=True)

    loaded = store.load("us_tech_etfs")
    assert loaded.tickers == ("AAPL", "MSFT")


def test_load_roundtrips_dataclass(tmp_path: Path) -> None:
    store = DynamicUniverseStore(tmp_path)
    original = _make_universe("us_tech_etfs")
    store.save(original)

    loaded = store.load("us_tech_etfs")

    assert loaded == original


def test_list_loaded_sorted(tmp_path: Path) -> None:
    store = DynamicUniverseStore(tmp_path)
    store.save(_make_universe("zeta"))
    store.save(_make_universe("alpha"))

    assert store.list_loaded() == ["alpha", "zeta"]


def test_list_loaded_empty_when_dir_missing(tmp_path: Path) -> None:
    store = DynamicUniverseStore(tmp_path / "missing")
    assert store.list_loaded() == []
