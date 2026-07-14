"""Tests for realtime bar sources."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import MagicMock

from quant_trader.core.types import Bar
from quant_trader.live import IBKRBarSource, MockBarSource, RealtimeBarSource


def _bar(close: float = 101.0) -> Bar:
    return Bar(
        timestamp=datetime(2026, 7, 14, 10, 0, 0),
        open=100.0,
        high=102.0,
        low=99.0,
        close=close,
        adjusted_close=close,
        volume=1000,
    )


def test_mock_bar_source_subscribe_records_ticker() -> None:
    source = MockBarSource()
    source.subscribe("SPY")
    assert source._subscribed == {"SPY"}


def test_mock_bar_source_inject_then_next_returns_bar() -> None:
    source = MockBarSource()
    expected = _bar()
    source._inject(expected)
    actual = asyncio.run(source.next_bar())
    assert actual == expected


def test_mock_bar_source_next_waits_for_injection() -> None:
    source = MockBarSource()
    expected = _bar(105.0)

    async def consume() -> Bar:
        task = asyncio.create_task(source.next_bar())
        await asyncio.sleep(0)
        assert not task.done()
        source._inject(expected)
        return await task

    assert asyncio.run(consume()) == expected


def test_ibkr_bar_source_constructs_with_injected_client() -> None:
    source = IBKRBarSource(MagicMock())
    assert isinstance(source, RealtimeBarSource)
    source.stop()


def test_mock_bar_source_satisfies_protocol() -> None:
    assert isinstance(MockBarSource(), RealtimeBarSource)
