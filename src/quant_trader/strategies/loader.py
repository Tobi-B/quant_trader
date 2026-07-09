"""StrategyLoader: YAML-based loader with class registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from quant_trader.core.logging import get_logger
from quant_trader.strategies.base import MultiTickerStrategyBase, StrategyBase
from quant_trader.strategies.errors import (
    StrategyConfigError,
    StrategyError,
    UnknownStrategyError,
)

log = get_logger(__name__)


class StrategyLoader:
    """Loads strategy instances from a YAML config via a class registry.

    Concrete strategy classes are added with `register(cls)`. The registry
    key is the class's `name` ClassVar. The YAML file maps a strategy name
    to a `params` mapping; values are merged with the class's
    `default_params` and passed to the constructor.
    """

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._registry: dict[str, type[StrategyBase | MultiTickerStrategyBase]] = {}
        self._config: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def register(self, cls: type[StrategyBase | MultiTickerStrategyBase]) -> None:
        if not (issubclass(cls, StrategyBase) or issubclass(cls, MultiTickerStrategyBase)):
            raise StrategyError(
                f"{cls.__name__} muss von StrategyBase oder MultiTickerStrategyBase erben"
            )
        if not cls.name:
            raise StrategyError(f"{cls.__name__}.name ClassVar ist leer")
        existing = self._registry.get(cls.name)
        if existing is not None and existing is not cls:
            raise StrategyError(
                f"Strategy-Name '{cls.name}' bereits registriert: "
                f"{existing.__name__} vs {cls.__name__}"
            )
        self._registry[cls.name] = cls

    def registered_names(self) -> list[str]:
        return sorted(self._registry.keys())

    def is_registered(self, name: str) -> bool:
        return name in self._registry

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self._config_path.exists():
            raise StrategyConfigError(f"Strategie-Config nicht gefunden: {self._config_path}")
        with self._config_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        if not isinstance(raw, dict):
            raise StrategyConfigError(
                f"Strategie-Config muss ein Mapping sein, ist: {type(raw).__name__}"
            )
        for section_name, payload in raw.items():
            if not isinstance(payload, dict):
                raise StrategyConfigError(
                    f"Section '{section_name}' muss ein Mapping sein, ist: {type(payload).__name__}"
                )
            self._config[section_name] = dict(payload.get("params", {}))
        self._loaded = True

    def load(
        self,
        name: str,
        ticker: str = "",
    ) -> StrategyBase | MultiTickerStrategyBase:
        self._ensure_loaded()
        if name not in self._registry:
            raise UnknownStrategyError(name, self.registered_names())
        if name not in self._config:
            raise StrategyConfigError(
                f"Strategie '{name}' nicht in {self._config_path} konfiguriert"
            )
        params = self._config[name]
        cls = self._registry[name]
        if issubclass(cls, StrategyBase):
            instance: StrategyBase | MultiTickerStrategyBase = cls(ticker=ticker, params=params)
        else:
            instance = cls(params=params)
        log.info(
            "strategy.loaded",
            name=name,
            ticker=ticker,
            cls=type(instance).__name__,
            param_count=len(params),
        )
        return instance
