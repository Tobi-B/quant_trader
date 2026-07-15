"""Smoke test: dashboard script loads without import errors."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def test_dashboard_script_loads() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "backtest_dashboard.py"
    spec = importlib.util.spec_from_file_location("backtest_dashboard", script)
    assert spec is not None
    assert spec.loader is not None
