"""Tests for PresetRepository."""

from __future__ import annotations

from pathlib import Path

import pytest

from quant_trader.universe import PresetNotFoundError, PresetRepository


def _write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_repository_loads_presets_from_yaml(tmp_path: Path) -> None:
    cfg = tmp_path / "presets.yaml"
    _write_yaml(
        cfg,
        """
sp500:
  description: "Test S&P 500"
  tickers:
    - AAPL
    - MSFT
etfs:
  description: "Test ETFs"
  tickers:
    - SPY
""",
    )
    repo = PresetRepository(cfg)

    sp500 = repo.get("sp500")
    assert sp500.name == "sp500"
    assert sp500.description == "Test S&P 500"
    assert sp500.tickers == ("AAPL", "MSFT")

    assert [p.name for p in repo.all()] == ["sp500", "etfs"]
    assert repo.names() == ["etfs", "sp500"]


def test_repository_missing_file_yields_empty(tmp_path: Path) -> None:
    repo = PresetRepository(tmp_path / "does-not-exist.yaml")

    assert repo.all() == []
    assert repo.names() == []


def test_repository_unknown_preset_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "presets.yaml"
    _write_yaml(cfg, "sp500:\n  tickers: [AAPL]\n")
    repo = PresetRepository(cfg)

    with pytest.raises(PresetNotFoundError) as exc:
        repo.get("dax40")
    assert exc.value.name == "dax40"


def test_repository_loads_only_once(tmp_path: Path) -> None:
    cfg = tmp_path / "presets.yaml"
    _write_yaml(cfg, "sp500:\n  tickers: [AAPL]\n")
    repo = PresetRepository(cfg)
    repo.get("sp500")

    cfg.unlink()
    assert repo.names() == ["sp500"]


def test_repository_default_description_is_empty(tmp_path: Path) -> None:
    cfg = tmp_path / "presets.yaml"
    _write_yaml(cfg, "sp500:\n  tickers: [AAPL]\n")
    repo = PresetRepository(cfg)

    assert repo.get("sp500").description == ""
