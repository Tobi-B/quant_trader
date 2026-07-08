"""YAML-based preset repository."""

from __future__ import annotations

from pathlib import Path

import yaml

from quant_trader.core.types import Preset


class PresetNotFoundError(KeyError):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class PresetRepository:
    def __init__(self, config_path: Path) -> None:
        self._path = config_path
        self._presets: dict[str, Preset] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self._path.exists():
            self._loaded = True
            return
        with self._path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        for name, payload in raw.items():
            self._presets[name] = Preset(
                name=name,
                description=str(payload.get("description", "")),
                tickers=tuple(str(t) for t in payload.get("tickers", [])),
            )
        self._loaded = True

    def get(self, name: str) -> Preset:
        self._ensure_loaded()
        if name not in self._presets:
            raise PresetNotFoundError(name)
        return self._presets[name]

    def all(self) -> list[Preset]:
        self._ensure_loaded()
        return list(self._presets.values())

    def names(self) -> list[str]:
        self._ensure_loaded()
        return sorted(self._presets.keys())