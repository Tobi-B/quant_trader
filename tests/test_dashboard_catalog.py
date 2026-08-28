"""Tests for the dashboard "Katalog" tab wiring (Slice 1.7)."""

from __future__ import annotations

import re
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "backtest_dashboard.py"


def _load_dashboard_source() -> str:
    return _SCRIPT_PATH.read_text(encoding="utf-8")


def test_dashboard_imports_catalog_service() -> None:
    source = _load_dashboard_source()
    assert "InstrumentCatalogService" in source
    assert "DynamicUniverseStore" in source


def test_dashboard_has_katalog_tab() -> None:
    source = _load_dashboard_source()
    assert '"Katalog"' in source
    assert "_render_catalog_tab" in source


def test_dashboard_catalog_tab_between_cache_and_strategien() -> None:
    source = _load_dashboard_source()
    labels_block = source[
        source.index("tab_labels = [") : source.index("]", source.index("tab_labels = ["))
    ]
    assert labels_block.index("_CACHE_TAB") < labels_block.index("_CATALOG_TAB")
    assert labels_block.index("_CATALOG_TAB") < labels_block.index("_STRATEGIES_TAB")


def test_dashboard_catalog_handles_unavailable_catalog_in_german() -> None:
    source = _load_dashboard_source()
    assert "CatalogUnavailableError" in source
    assert "noch nicht verfuegbar" in source


def test_dashboard_catalog_standard_universe_buttons() -> None:
    source = _load_dashboard_source()
    assert 'build_standard_universe("dax40")' in source
    assert 'build_standard_universe("etfs")' in source
    assert "S&P 500 bleibt statisch" in source


def test_dashboard_uses_public_catalog_provider_not_fmp() -> None:
    """The catalog must not be wired to FMP: its list endpoints are paywalled."""
    source = _load_dashboard_source()
    assert "PublicCatalogProvider()" in source
    assert "InstrumentCatalogService(\n        FinancialModellingPrepProvider" not in source


def test_dashboard_catalog_confirms_overwrite() -> None:
    source = _load_dashboard_source()
    assert "existiert bereits. Ersetzen?" in source
    assert "catalog_pending_overwrite" in source


def test_dashboard_catalog_selectboxes_and_multiselects_have_keys() -> None:
    source = _load_dashboard_source()
    offending: list[str] = []
    pattern = re.compile(r"\.(selectbox|multiselect|radio)\(")
    for match in pattern.finditer(source):
        start = match.end()
        depth = 1
        index = start
        while index < len(source) and depth > 0:
            char = source[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1
        call = source[start : index - 1]
        if "key=" not in call:
            line_number = source.count("\n", 0, match.start()) + 1
            offending.append(f"  line {line_number}: {match.group()} ...")
    assert not offending, "Widgets ohne expliziten key=:\n" + "\n".join(offending)
