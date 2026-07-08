"""Tests for UniverseStore."""

from __future__ import annotations

from pathlib import Path

from quant_trader.core.types import Preset
from quant_trader.universe import StoreResult, UniverseStore


def _make_preset(name: str, tickers: tuple[str, ...]) -> Preset:
    return Preset(name=name, description=f"Test {name}", tickers=tickers)


def test_store_path_for(tmp_path: Path) -> None:
    store = UniverseStore(tmp_path)

    assert store.path_for("sp500") == tmp_path / "universe" / "sp500.csv"


def test_store_exists_false_initially(tmp_path: Path) -> None:
    store = UniverseStore(tmp_path)
    assert store.exists("sp500") is False


def test_store_save_creates_csv_with_header_and_tickers(tmp_path: Path) -> None:
    store = UniverseStore(tmp_path)
    preset = _make_preset("sp500", ("AAPL", "MSFT", "GOOGL"))

    result = store.save(preset)

    assert isinstance(result, StoreResult)
    assert result.written == 3
    assert result.skipped is False
    assert result.path.exists()

    content = result.path.read_text(encoding="utf-8").splitlines()
    assert content[0] == "ticker"
    assert content[1:] == ["AAPL", "MSFT", "GOOGL"]


def test_store_save_is_idempotent_when_exists(tmp_path: Path) -> None:
    store = UniverseStore(tmp_path)
    preset = _make_preset("sp500", ("AAPL", "MSFT"))

    first = store.save(preset)
    second = store.save(_make_preset("sp500", ("AAPL", "MSFT", "EXTRA")))

    assert first.skipped is False
    assert second.skipped is True
    assert second.written == 0
    assert first.path.read_text(encoding="utf-8").splitlines() == ["ticker", "AAPL", "MSFT"]


def test_store_creates_parent_directories(tmp_path: Path) -> None:
    store = UniverseStore(tmp_path / "deep" / "nested")
    preset = _make_preset("etfs", ("SPY",))

    result = store.save(preset)

    assert result.path.exists()
    assert result.path.parent.is_dir()
