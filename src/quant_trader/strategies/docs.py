"""StrategyDocLoader: loads per-strategy README markdown files.

The dashboard renders the README files placed under `docs/strategies/`
(next to the project root) directly in the "Strategien" tab. Each file
is named after the strategy's `name` ClassVar plus a `.md` suffix.
"""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class StrategyDocLoader:
    """Reads per-strategy README markdown files from a docs directory."""

    def __init__(self, docs_dir: Path) -> None:
        if docs_dir.is_absolute():
            self._dir = docs_dir
        else:
            self._dir = _PROJECT_ROOT / docs_dir

    def load(self, strategy_name: str) -> str | None:
        """Read `docs/strategies/<strategy_name>.md`.

        Returns the file content as UTF-8 text, or `None` if the file is
        missing.
        """
        path = self._dir / f"{strategy_name}.md"
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            return fh.read()

    def list_documented(self) -> list[str]:
        """Return sorted strategy names (stems) of all `.md` files in the dir.

        Returns an empty list if the directory does not exist.
        """
        if not self._dir.exists():
            return []
        return sorted(p.stem for p in self._dir.glob("*.md"))

    def has_doc(self, strategy_name: str) -> bool:
        """Quick existence check without reading the file."""
        return (self._dir / f"{strategy_name}.md").exists()


__all__ = ["StrategyDocLoader"]
