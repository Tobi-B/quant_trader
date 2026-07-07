"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_ticker() -> str:
    return "SPY"
