"""Tests for dashboard company-search wiring."""

from __future__ import annotations

from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "backtest_dashboard.py"


def _load_dashboard_source() -> str:
    return _SCRIPT_PATH.read_text(encoding="utf-8")


def test_dashboard_imports_company_search_service() -> None:
    source = _load_dashboard_source()
    assert "CompanySearchService" in source
    assert "FinancialModellingPrepProvider" in source


def test_dashboard_renders_search_in_custom_ticker_mode() -> None:
    source = _load_dashboard_source()
    assert "_render_instrument_search(search_service)" in source
    assert '"Unternehmen suchen"' in source
    assert '"Auswahl übernehmen"' in source


def test_dashboard_passes_selected_ticker_to_runner() -> None:
    source = _load_dashboard_source()
    assert '_TICKER_KEY = "run_ticker"' in source
    assert "ticker=ticker" in source


def test_dashboard_handles_unavailable_search_in_german() -> None:
    source = _load_dashboard_source()
    assert "SearchUnavailableError" in source
    assert "Die Unternehmenssuche ist vorübergehend nicht verfügbar." in source
