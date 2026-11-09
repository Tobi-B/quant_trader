"""Tests for InstrumentCatalogSnapshotStore."""

from __future__ import annotations

import os
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd

from quant_trader.data.instrument_catalog import InstrumentCatalogSnapshotStore


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "exchange": "NASDAQ",
                "exchange_full_name": "NASDAQ Global Select",
                "currency": "USD",
                "instrument_type": "stock",
                "country": "US",
                "sector": "Technology",
                "is_active": True,
            }
        ]
    )


def test_exists_false_initially(tmp_path: Path) -> None:
    store = InstrumentCatalogSnapshotStore(tmp_path / "catalog" / "instruments.parquet")
    assert store.exists() is False
    assert store.read() is None
    assert store.latest_snapshot_id() is None
    assert store.snapshot_age() is None


def test_write_creates_parent_dirs_and_is_readable(tmp_path: Path) -> None:
    path = tmp_path / "catalog" / "instruments.parquet"
    store = InstrumentCatalogSnapshotStore(path)

    store.write(_df(), "snap-1")

    assert path.exists()
    df = store.read()
    assert df is not None
    assert list(df["ticker"]) == ["AAPL"]
    assert store.latest_snapshot_id() == "snap-1"


def test_write_is_atomic_no_tmp_file_left_behind(tmp_path: Path) -> None:
    path = tmp_path / "instruments.parquet"
    store = InstrumentCatalogSnapshotStore(path)

    store.write(_df(), "snap-1")

    leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


def test_needs_refresh_true_without_snapshot(tmp_path: Path) -> None:
    store = InstrumentCatalogSnapshotStore(tmp_path / "instruments.parquet")
    assert store.needs_refresh(timedelta(hours=24)) is True


def test_needs_refresh_false_for_fresh_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "instruments.parquet"
    store = InstrumentCatalogSnapshotStore(path)
    store.write(_df(), "snap-1")

    assert store.needs_refresh(timedelta(hours=24)) is False


def test_needs_refresh_true_for_stale_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "instruments.parquet"
    store = InstrumentCatalogSnapshotStore(path)
    store.write(_df(), "snap-1")

    old = time.time() - timedelta(hours=48).total_seconds()
    os.utime(path, (old, old))

    assert store.needs_refresh(timedelta(hours=24)) is True
    age = store.snapshot_age()
    assert age is not None
    assert age >= timedelta(hours=47)
