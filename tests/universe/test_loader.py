"""Tests for UniverseLoader."""

from __future__ import annotations

from pathlib import Path

import pytest

from quant_trader.core.types import Preset
from quant_trader.universe import (
    PresetNotFoundError,
    PresetRepository,
    UniverseLoader,
    UniverseStore,
)


@pytest.fixture
def repo_with_preset(tmp_path: Path) -> PresetRepository:
    cfg = tmp_path / "presets.yaml"
    cfg.write_text(
        "sp500:\n  description: Test\n  tickers: [AAPL, MSFT]\n",
        encoding="utf-8",
    )
    return PresetRepository(cfg)


@pytest.fixture
def store(tmp_path: Path) -> UniverseStore:
    return UniverseStore(tmp_path)


def test_loader_writes_preset_when_missing(
    repo_with_preset: PresetRepository, store: UniverseStore
) -> None:
    loader = UniverseLoader(repo_with_preset, store)

    result = loader.load("sp500")

    assert result.written == 2
    assert result.skipped is False
    assert store.exists("sp500")


def test_loader_skips_when_already_loaded(
    repo_with_preset: PresetRepository, store: UniverseStore
) -> None:
    loader = UniverseLoader(repo_with_preset, store)
    loader.load("sp500")
    preset = Preset(name="sp500", description="", tickers=("AAPL", "MSFT", "EXTRA"))
    store.save(preset)

    result = loader.load("sp500")

    assert result.skipped is True
    assert result.written == 0


def test_loader_unknown_preset_raises(
    repo_with_preset: PresetRepository, store: UniverseStore
) -> None:
    loader = UniverseLoader(repo_with_preset, store)

    with pytest.raises(PresetNotFoundError):
        loader.load("dax40")


def test_loader_list_loaded_only_returns_existing(
    repo_with_preset: PresetRepository, store: UniverseStore
) -> None:
    loader = UniverseLoader(repo_with_preset, store)
    loader.load("sp500")

    assert loader.list_loaded() == ["sp500"]


def test_loader_list_loaded_empty_when_nothing_saved(
    repo_with_preset: PresetRepository, store: UniverseStore
) -> None:
    loader = UniverseLoader(repo_with_preset, store)

    assert loader.list_loaded() == []
