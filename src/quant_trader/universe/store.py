"""Universe store - writes ticker lists to CSV."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quant_trader.core.types import Preset


@dataclass(frozen=True)
class StoreResult:
    path: Path
    written: int
    skipped: bool


class UniverseStore:
    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir

    def path_for(self, preset_name: str) -> Path:
        return self._base / "universe" / f"{preset_name}.csv"

    def exists(self, preset_name: str) -> bool:
        return self.path_for(preset_name).exists()

    def save(self, preset: Preset) -> StoreResult:
        target = self.path_for(preset.name)
        if target.exists():
            return StoreResult(path=target, written=0, skipped=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as f:
            f.write("ticker\n")
            for ticker in preset.tickers:
                f.write(f"{ticker}\n")
        return StoreResult(path=target, written=len(preset.tickers), skipped=False)