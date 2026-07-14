"""Tests for the project .dockerignore file."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERIGNORE = REPO_ROOT / ".dockerignore"


def test_dockerignore_excludes_venv_and_cache_and_env() -> None:
    assert DOCKERIGNORE.exists(), f".dockerignore not found at {DOCKERIGNORE}"
    lines = {line.strip() for line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()}
    lines.discard("")

    required = {
        ".venv/",
        "__pycache__/",
        ".git/",
        ".env",
        "data/",
        "reports/",
    }
    missing = required - lines
    assert not missing, f".dockerignore missing entries: {sorted(missing)}"
