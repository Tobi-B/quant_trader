"""Tests for docker-compose.yml."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"


def test_compose_file_is_valid_yaml_and_has_qtrader_service() -> None:
    assert COMPOSE_FILE.exists(), f"docker-compose.yml not found at {COMPOSE_FILE}"
    data = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    services = data.get("services")
    assert isinstance(services, dict)
    assert "qtrader" in services
    qtrader = services["qtrader"]
    assert isinstance(qtrader, dict)
    assert qtrader.get("build") == "."
    assert qtrader.get("container_name") == "quant-trader"
    assert "8501:8501" in str(qtrader.get("ports", []))
