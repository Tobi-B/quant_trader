"""Tests for Settings.strategy_docs_dir (Slice 2.6)."""

from __future__ import annotations

from pathlib import Path

from quant_trader.core.config import Settings


def test_settings_has_strategy_docs_dir_default() -> None:
    settings = Settings()
    assert settings.strategy_docs_dir == Path("./docs/strategies")


def test_settings_strategy_docs_dir_is_path() -> None:
    settings = Settings()
    assert isinstance(settings.strategy_docs_dir, Path)


def test_settings_strategy_docs_dir_can_be_overridden(tmp_path: Path) -> None:
    settings = Settings(strategy_docs_dir=tmp_path / "custom-docs")
    assert settings.strategy_docs_dir == tmp_path / "custom-docs"
