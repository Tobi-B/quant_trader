"""Tests for StrategyDocLoader (per-strategy README markdown loader)."""

from __future__ import annotations

from pathlib import Path

import pytest

from quant_trader.strategies import StrategyDocLoader


def _write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_loader_loads_existing_md_file(tmp_path: Path) -> None:
    _write_md(tmp_path / "sma_cross.md", "# SMA Cross\n\nTrivial-Trendfolge.")
    loader = StrategyDocLoader(tmp_path)
    assert loader.load("sma_cross") == "# SMA Cross\n\nTrivial-Trendfolge."


def test_loader_returns_none_for_missing_file(tmp_path: Path) -> None:
    loader = StrategyDocLoader(tmp_path)
    assert loader.load("nonexistent") is None


def test_loader_lists_documented_strategies(tmp_path: Path) -> None:
    _write_md(tmp_path / "sma_cross.md", "# a")
    _write_md(tmp_path / "momentum.md", "# b")
    _write_md(tmp_path / "etf_rotation.md", "# c")
    loader = StrategyDocLoader(tmp_path)
    assert loader.list_documented() == ["etf_rotation", "momentum", "sma_cross"]


def test_loader_handles_empty_docs_dir(tmp_path: Path) -> None:
    loader = StrategyDocLoader(tmp_path)
    assert loader.list_documented() == []


def test_loader_handles_missing_docs_dir(tmp_path: Path) -> None:
    loader = StrategyDocLoader(tmp_path / "does_not_exist")
    assert loader.list_documented() == []


def test_loader_reads_md_with_unicode(tmp_path: Path) -> None:
    content = "# Strategie\n\nUeberkauft, schwaecherer Trend, aeusserst volatil."
    _write_md(tmp_path / "rsi_mean_reversion.md", content)
    loader = StrategyDocLoader(tmp_path)
    assert loader.load("rsi_mean_reversion") == content


def test_loader_strips_md_extension(tmp_path: Path) -> None:
    _write_md(tmp_path / "sma_cross.md", "x")
    loader = StrategyDocLoader(tmp_path)
    assert "sma_cross" in loader.list_documented()
    assert "sma_cross.md" not in loader.list_documented()


def test_loader_has_doc_returns_true_for_existing(tmp_path: Path) -> None:
    _write_md(tmp_path / "sma_cross.md", "x")
    loader = StrategyDocLoader(tmp_path)
    assert loader.has_doc("sma_cross") is True
    assert loader.has_doc("missing") is False


def test_loader_ignores_non_md_files(tmp_path: Path) -> None:
    _write_md(tmp_path / "sma_cross.md", "x")
    _write_md(tmp_path / "notes.txt", "ignore me")
    loader = StrategyDocLoader(tmp_path)
    assert loader.list_documented() == ["sma_cross"]


def test_loader_reads_empty_md_as_empty_string(tmp_path: Path) -> None:
    _write_md(tmp_path / "empty.md", "")
    loader = StrategyDocLoader(tmp_path)
    assert loader.load("empty") == ""


def test_loader_resolves_relative_path_against_project_root(tmp_path: Path) -> None:
    loader = StrategyDocLoader(Path("./docs/strategies"))
    docs_root = loader._dir
    assert docs_root.is_absolute()
    assert docs_root.name == "strategies"


def test_loader_keeps_absolute_path_unchanged(tmp_path: Path) -> None:
    loader = StrategyDocLoader(tmp_path)
    assert loader._dir == tmp_path


@pytest.mark.parametrize(
    "name",
    ["sma_cross", "momentum", "rsi_mean_reversion", "etf_rotation"],
)
def test_loader_roundtrip_for_registered_strategy_names(tmp_path: Path, name: str) -> None:
    _write_md(tmp_path / f"{name}.md", f"# {name}\n\nBeispiel-README.")
    loader = StrategyDocLoader(tmp_path)
    assert loader.has_doc(name) is True
    assert loader.load(name) is not None
    assert name in loader.list_documented()
