"""Smoke test: dashboard script loads without import errors."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "scripts" / "backtest_dashboard.py"


def test_dashboard_script_loads() -> None:
    spec = importlib.util.spec_from_file_location("backtest_dashboard", _DASHBOARD_PATH)
    assert spec is not None
    assert spec.loader is not None


def test_dashboard_selectboxes_have_unique_keys() -> None:
    source = _DASHBOARD_PATH.read_text(encoding="utf-8")
    offending: list[str] = []
    pattern = re.compile(r"\.selectbox\(")
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
    assert not offending, (
        "st.selectbox ohne expliziten key produziert eine StreamlitDuplicateElementId-"
        "Exception, sobald mehrere Tabs dieselbe Sidebar-Komponente registrieren. "
        "Bitte fuer jeden st.selectbox-Aufruf einen eindeutigen key= setzen:\n"
        + "\n".join(offending)
    )
