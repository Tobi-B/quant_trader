"""Tests for fetch_data CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from quant_trader.data.cli import main


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cfg = tmp_path / "presets.yaml"
    cfg.write_text("etfs:\n  description: T\n  tickers: [SPY, VOO]\n", encoding="utf-8")
    monkeypatch.setenv("UNIVERSE_PRESETS_PATH", str(cfg))
    monkeypatch.setenv("ALPHAVANTAGE_KEY", "")
    monkeypatch.setenv("STOCKDATA_API_TOKEN", "")
    from quant_trader.core.config import get_settings

    get_settings.cache_clear()
    return tmp_path


def test_cli_requires_ticker_or_universe(isolated: Path) -> None:
    with pytest.raises(SystemExit):
        main([])


def test_cli_unknown_preset_returns_1(isolated: Path) -> None:
    rc = main(["--universe", "does-not-exist"])
    assert rc == 1


def test_cli_universe_loads_with_mocked_provider(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime

    from quant_trader.core.types import Bar, Granularity

    class _StubProvider:
        name = "stub"

        def __init__(self) -> None:
            self.calls: list[str] = []

        def fetch(self, ticker: str, start: Any, end: Any, granularity: Any) -> list[Bar]:
            self.calls.append(ticker)
            return [
                Bar(
                    timestamp=datetime(2024, 1, 2, 16, 0),
                    open=1.0,
                    high=2.0,
                    low=0.5,
                    close=1.5,
                    adjusted_close=1.5,
                    volume=100,
                )
            ]

    stub = _StubProvider()
    monkeypatch.setattr("quant_trader.data.cli.build_chain", lambda settings: stub)

    rc = main(["--universe", "etfs", "--start", "2024-01-02", "--end", "2024-01-05"])

    assert rc == 0
    assert stub.calls == ["SPY", "VOO"]
    assert (isolated / "raw" / "daily" / "SPY.parquet").exists()
    assert (isolated / "raw" / "daily" / "VOO.parquet").exists()


def test_cli_unknown_ticker_returns_1(isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from quant_trader.core.errors import TickerNotFoundError

    class _FailProvider:
        name = "fail"

        def fetch(self, *args: object, **kwargs: object) -> list[Any]:
            raise TickerNotFoundError("ZZZZZ")

    monkeypatch.setattr("quant_trader.data.cli.build_chain", lambda settings: _FailProvider())

    rc = main(["ZZZZZ", "--start", "2024-01-02", "--end", "2024-01-05"])

    assert rc == 1