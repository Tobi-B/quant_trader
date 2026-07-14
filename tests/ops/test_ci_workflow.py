"""Tests for the GitHub Actions CI workflow."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_yaml_has_test_and_docker_jobs() -> None:
    assert WORKFLOW_FILE.exists(), f"ci.yml not found at {WORKFLOW_FILE}"
    data = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    jobs = data.get("jobs")
    assert isinstance(jobs, dict)
    assert "test" in jobs
    assert "docker" in jobs
    assert data.get("name") == "ci"
