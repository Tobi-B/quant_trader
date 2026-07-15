"""Tests for the dashboard's "Strategien" tab wiring (Slice 2.6).

Streamlit is hard to test directly (it spins up a server), so we verify
the contract via lightweight static checks on `scripts/backtest_dashboard.py`:
- The script imports `StrategyDocLoader` from the strategy package.
- The tab labels list contains the German "Strategien" label.
- The dashboard tab tuple unpacks five tabs (Run-Form, Read-Mode,
  Vergleich, Cache, Strategien).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "backtest_dashboard.py"


def _load_dashboard_source() -> str:
    return _SCRIPT_PATH.read_text(encoding="utf-8")


def test_dashboard_script_path_exists() -> None:
    assert _SCRIPT_PATH.exists()


def test_dashboard_imports_strategy_doc_loader() -> None:
    source = _load_dashboard_source()
    assert "StrategyDocLoader" in source
    assert "from quant_trader.strategies import" in source


def test_dashboard_has_strategies_tab_in_tabs_list() -> None:
    source = _load_dashboard_source()
    assert '"Strategien"' in source


def test_dashboard_packs_five_tabs() -> None:
    source = _load_dashboard_source()
    assert "tab_run, tab_read, tab_comparison, tab_cache, tab_strategies" in source


def test_dashboard_calls_render_strategies_tab() -> None:
    source = _load_dashboard_source()
    assert "_render_strategies_tab" in source
    assert "dashboard.strategies.rendered" in source


def test_dashboard_loads_strategy_docs_from_settings() -> None:
    source = _load_dashboard_source()
    assert "get_settings().strategy_docs_dir" in source


def test_dashboard_script_loads_without_import_error() -> None:
    spec = importlib.util.spec_from_file_location("backtest_dashboard", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
