"""Tests for universe CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from quant_trader.universe.cli import main


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
