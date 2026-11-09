"""Tests for the Run-Form / Read-Mode dashboard fixes.

Covers three issues found while reviewing slice 1.7:
- The Ticker field was shown (and silently ignored) for multi-ticker
  strategies, since StrategyLoader.load() never passes `ticker` to them.
- The Universe-Preset selector was shown even for strategies that cannot
  honour it (single-ticker strategies, and long_capital_short_labor after
  its own supports_universe_override fix).
- Read-Mode's controls were written into the global st.sidebar
  unconditionally, so they stayed visible on top of the Run-Form controls
  regardless of which tab was active.
"""

from __future__ import annotations

from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "backtest_dashboard.py"


def _load_dashboard_source() -> str:
    return _SCRIPT_PATH.read_text(encoding="utf-8")


def test_run_form_branches_on_strategy_shape() -> None:
    source = _load_dashboard_source()
    assert "is_single_ticker = issubclass(strategy_cls, StrategyBase)" in source
    assert "supports_override = bool(getattr(strategy_cls" in source


def test_run_form_uses_get_class_not_private_registry() -> None:
    source = _load_dashboard_source()
    assert "_registry[" not in source
    assert "get_class(" in source


def test_run_form_multi_ticker_without_override_shows_explanation() -> None:
    source = _load_dashboard_source()
    assert "kann hier nicht ueberschrieben werden" in source


def test_run_form_multi_ticker_with_override_has_strategy_default_option() -> None:
    source = _load_dashboard_source()
    assert '_STRATEGY_DEFAULT_UNIVERSE_OPTION = "(Strategie-Standard)"' in source


def _function_body(source: str, def_line: str) -> str:
    start = source.index(def_line)
    end = source.index("\ndef ", start + 1)
    return source[start:end]


def test_read_mode_controls_not_in_sidebar() -> None:
    source = _load_dashboard_source()
    body = _function_body(source, "def _render_read_mode(")
    assert "st.sidebar" not in body


def test_run_form_signature_takes_loader() -> None:
    source = _load_dashboard_source()
    body = _function_body(source, "def _render_run_form(")
    assert "loader: StrategyLoader" in body
