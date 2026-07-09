"""Tests for StrategyLoader registry + YAML loading."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

import pytest

from quant_trader.core.types import Bar
from quant_trader.strategies import (
    MultiTickerStrategyBase,
    PortfolioState,
    Signal,
    StrategyBase,
    StrategyConfigError,
    StrategyError,
    StrategyLoader,
    UnknownStrategyError,
)


def _bar(close: float = 100.0) -> Bar:
    return Bar(
        timestamp=datetime(2024, 1, 2, 16, 0),
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        adjusted_close=close,
        volume=1000,
    )


def _write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class _DummySingle(StrategyBase):
    name: ClassVar[str] = "dummy_single"
    default_params: ClassVar[dict[str, Any]] = {"threshold": 10}

    def warmup_bars(self) -> int:
        return 0

    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
        return []


class _DummyMulti(MultiTickerStrategyBase):
    name: ClassVar[str] = "dummy_multi"
    default_params: ClassVar[dict[str, Any]] = {"top_n": 1}

    def warmup_bars(self) -> int:
        return 0

    def on_universe_bars(
        self,
        timestamp: datetime,
        bars_by_ticker: dict[str, Bar],
        portfolio: PortfolioState,
    ) -> list[Signal]:
        return []


class _NotAStrategy:
    pass


def test_register_single_ticker_class(tmp_path: Path) -> None:
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummySingle)
    assert loader.registered_names() == ["dummy_single"]
    assert loader.is_registered("dummy_single") is True


def test_register_multi_ticker_class(tmp_path: Path) -> None:
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummyMulti)
    assert loader.registered_names() == ["dummy_multi"]


def test_register_mixed(tmp_path: Path) -> None:
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummySingle)
    loader.register(_DummyMulti)
    assert loader.registered_names() == ["dummy_multi", "dummy_single"]


def test_register_non_subclass_raises(tmp_path: Path) -> None:
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    with pytest.raises(StrategyError, match="muss von StrategyBase"):
        loader.register(_NotAStrategy)  # type: ignore[arg-type]


def test_register_class_with_empty_name_raises(tmp_path: Path) -> None:
    class _Anonymous(StrategyBase):
        name = ""

        def warmup_bars(self) -> int:
            return 0

        def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
            return []

    loader = StrategyLoader(tmp_path / "strategies.yaml")
    with pytest.raises(StrategyError, match="name ClassVar ist leer"):
        loader.register(_Anonymous)


def test_register_duplicate_name_raises(tmp_path: Path) -> None:
    class _Other(StrategyBase):
        name = "dummy_single"

        def warmup_bars(self) -> int:
            return 0

        def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
            return []

    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummySingle)
    with pytest.raises(StrategyError, match="bereits registriert"):
        loader.register(_Other)


def test_register_same_class_twice_is_idempotent(tmp_path: Path) -> None:
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummySingle)
    loader.register(_DummySingle)
    assert loader.registered_names() == ["dummy_single"]


def test_load_unknown_raises_with_available_list(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "strategies.yaml", "dummy_single:\n  params: {threshold: 5}\n")
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummySingle)

    with pytest.raises(UnknownStrategyError) as exc:
        loader.load("does_not_exist")
    assert exc.value.name == "does_not_exist"
    assert "dummy_single" in exc.value.available


def test_load_with_empty_registry_lists_none(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "strategies.yaml", "{}\n")
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    with pytest.raises(UnknownStrategyError) as exc:
        loader.load("any")
    assert exc.value.available == []


def test_load_missing_config_file_raises(tmp_path: Path) -> None:
    loader = StrategyLoader(tmp_path / "missing.yaml")
    loader.register(_DummySingle)
    with pytest.raises(StrategyConfigError, match="nicht gefunden"):
        loader.load("dummy_single")


def test_load_missing_section_raises(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "strategies.yaml", "other_strategy:\n  params: {}\n")
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummySingle)
    with pytest.raises(StrategyConfigError, match="nicht in"):
        loader.load("dummy_single")


def test_load_malformed_config_raises(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "strategies.yaml", "dummy_single: not-a-dict\n")
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummySingle)
    with pytest.raises(StrategyConfigError, match="muss ein Mapping sein"):
        loader.load("dummy_single")


def test_load_merges_params_with_defaults(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path / "strategies.yaml",
        """
dummy_single:
  params:
    threshold: 99
""",
    )
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummySingle)
    strategy = loader.load("dummy_single")
    assert isinstance(strategy, _DummySingle)
    assert strategy.params == {"threshold": 99}


def test_load_uses_default_when_no_params_in_yaml(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "strategies.yaml", "dummy_single: {}\n")
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummySingle)
    strategy = loader.load("dummy_single")
    assert strategy.params == {"threshold": 10}


def test_load_logs_strategy_loaded_event(tmp_path: Path) -> None:
    from structlog.testing import capture_logs

    _write_yaml(
        tmp_path / "strategies.yaml",
        """
dummy_single:
  params:
    threshold: 7
""",
    )
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummySingle)

    with capture_logs() as captured:
        loader.load("dummy_single")

    events = [entry["event"] for entry in captured]
    assert "strategy.loaded" in events
    matching = [e for e in captured if e["event"] == "strategy.loaded"]
    assert matching[0]["name"] == "dummy_single"
    assert matching[0]["cls"] == "_DummySingle"
    assert matching[0]["param_count"] == 1


def test_load_loads_config_only_once(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "strategies.yaml", "dummy_single: {}\n")
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummySingle)
    loader.load("dummy_single")

    (tmp_path / "strategies.yaml").unlink()
    strategy = loader.load("dummy_single")
    assert isinstance(strategy, _DummySingle)


def test_load_multi_ticker_strategy(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path / "strategies.yaml",
        """
dummy_multi:
  params:
    top_n: 3
""",
    )
    loader = StrategyLoader(tmp_path / "strategies.yaml")
    loader.register(_DummyMulti)
    strategy = loader.load("dummy_multi")
    assert isinstance(strategy, _DummyMulti)
    assert strategy.params == {"top_n": 3}
