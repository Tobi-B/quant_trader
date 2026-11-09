"""Dynamic universes: named, filter-built ticker lists persisted as JSON."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


class UniverseAlreadyExistsError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


@dataclass(frozen=True)
class DynamicUniverse:
    name: str
    built_from_snapshot: str
    created_at: datetime
    filter_description: str
    filters: dict[str, str]
    tickers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()
        payload["tickers"] = list(self.tickers)
        return payload

    @staticmethod
    def from_dict(payload: dict[str, object]) -> DynamicUniverse:
        raw_filters = payload.get("filters") or {}
        raw_tickers = payload.get("tickers") or []
        if not isinstance(raw_filters, dict):
            raise ValueError("'filters' must be an object")
        if not isinstance(raw_tickers, list):
            raise ValueError("'tickers' must be an array")
        return DynamicUniverse(
            name=str(payload["name"]),
            built_from_snapshot=str(payload["built_from_snapshot"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            filter_description=str(payload.get("filter_description", "")),
            filters={str(k): str(v) for k, v in raw_filters.items()},
            tickers=tuple(str(t) for t in raw_tickers),
        )


class DynamicUniverseStore:
    """Persists `DynamicUniverse` objects as one JSON file per name.

    Writes are atomic (temp file + `os.replace`), matching the pattern used
    by `InstrumentCatalogSnapshotStore` for the same reason: a crash
    mid-write must never leave a half-written universe file behind.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir

    def path_for(self, name: str) -> Path:
        return self._base / f"{name}.json"

    def exists(self, name: str) -> bool:
        return self.path_for(name).exists()

    def save(self, universe: DynamicUniverse, *, overwrite: bool = False) -> Path:
        target = self.path_for(universe.name)
        if target.exists() and not overwrite:
            raise UniverseAlreadyExistsError(universe.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
        tmp_path.write_text(
            json.dumps(universe.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp_path, target)
        return target

    def load(self, name: str) -> DynamicUniverse:
        target = self.path_for(name)
        payload = json.loads(target.read_text(encoding="utf-8"))
        return DynamicUniverse.from_dict(payload)

    def list_loaded(self) -> list[str]:
        if not self._base.exists():
            return []
        return sorted(p.stem for p in self._base.glob("*.json"))


__all__ = ["DynamicUniverse", "DynamicUniverseStore", "UniverseAlreadyExistsError"]
