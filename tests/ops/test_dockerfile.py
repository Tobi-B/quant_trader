"""Tests for the project Dockerfile."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile"


def _read_dockerfile() -> str:
    assert DOCKERFILE.exists(), f"Dockerfile not found at {DOCKERFILE}"
    return DOCKERFILE.read_text(encoding="utf-8")


def test_dockerfile_exists_and_has_multistage() -> None:
    content = _read_dockerfile()
    assert "AS builder" in content
    assert "AS runtime" in content
    assert "FROM python:3.12-slim AS builder" in content
    assert "FROM python:3.12-slim AS runtime" in content


def test_dockerfile_exposes_8501() -> None:
    content = _read_dockerfile()
    assert "EXPOSE 8501" in content
    assert "--server.address" in content
    assert "0.0.0.0" in content
    assert "streamlit" in content.lower()
    assert "scripts/backtest_dashboard.py" in content


def test_dockerfile_installs_with_uv() -> None:
    content = _read_dockerfile()
    assert "install" in content
    assert "uv" in content
    assert "uv pip install" in content
    assert ".[ui,dev]" in content
