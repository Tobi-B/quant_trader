"""Universe loader - orchestrates preset fetch + store."""

from __future__ import annotations

from quant_trader.core.logging import get_logger
from quant_trader.universe.presets import PresetRepository
from quant_trader.universe.store import StoreResult, UniverseStore

log = get_logger(__name__)


class UniverseLoader:
    def __init__(self, presets: PresetRepository, store: UniverseStore) -> None:
        self._presets = presets
        self._store = store

    def load(self, preset_name: str) -> StoreResult:
        preset = self._presets.get(preset_name)
        if self._store.exists(preset.name):
            log.info("universe.exists", name=preset.name)
            return StoreResult(
                path=self._store.path_for(preset.name),
                written=0,
                skipped=True,
            )
        result = self._store.save(preset)
        log.info("universe.loaded", name=preset.name, count=result.written)
        return result

    def list_loaded(self) -> list[str]:
        return [name for name in self._presets.names() if self._store.exists(name)]
