"""Tests for the asynchronous live loop."""

from __future__ import annotations

import asyncio
import contextlib
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from quant_trader.core.types import Bar
from quant_trader.live import (
    DailySummary,
    LiveLoop,
    MockBarSource,
    MockBroker,
    ReconnectConfig,
    TradeJournal,
)
from quant_trader.strategies import Action, PortfolioState, Signal, StrategyBase


class _SequenceStrategy(StrategyBase):
    name = "sequence"

    def __init__(self, actions: list[Action]) -> None:
        super().__init__(ticker="SPY")
        self._actions = actions
        self.calls = 0

    def warmup_bars(self) -> int:
        return 0

    def on_bar(self, bar: Bar, portfolio: PortfolioState) -> list[Signal]:
        self.calls += 1
        if not self._actions:
            return []
        action = self._actions.pop(0)
        return [Signal(timestamp=bar.timestamp, ticker=self.ticker, action=action)]


def _bar(minute: int) -> Bar:
    return Bar(
        timestamp=datetime(2026, 7, 14, 10, minute, 0),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        adjusted_close=100.0,
        volume=1000,
    )


def _finite_source(*bars: Bar) -> MockBarSource:
    source = MockBarSource()
    for bar in bars:
        source._inject(bar)
    source.stop()
    return source


def _run_loop(
    db_path: Path,
    strategy: _SequenceStrategy,
    source: MockBarSource,
    broker: MockBroker | None = None,
    duration: timedelta | None = None,
):
    loop = LiveLoop(
        strategy=strategy,
        broker=broker or MockBroker(),
        source=source,
        journal=TradeJournal(db_path),
        run_id="run-5.2",
        duration=duration,
    )
    return asyncio.run(loop.run())


def test_loop_runs_until_duration(tmp_path: Path) -> None:
    strategy = _SequenceStrategy([])
    summary = _run_loop(
        tmp_path / "trades.sqlite",
        strategy,
        MockBarSource(),
        duration=timedelta(milliseconds=1),
    )
    assert summary.run_id == "run-5.2"
    assert summary.total_signals == 0
    assert strategy.calls == 0


def test_loop_invokes_strategy_for_each_bar(tmp_path: Path) -> None:
    strategy = _SequenceStrategy([])
    _run_loop(
        tmp_path / "trades.sqlite",
        strategy,
        _finite_source(_bar(0), _bar(1)),
    )
    assert strategy.calls == 2


def test_loop_places_buy_order_and_journals_trade(tmp_path: Path) -> None:
    db_path = tmp_path / "trades.sqlite"
    strategy = _SequenceStrategy([Action.BUY])
    broker = MockBroker(fill_price=101.5)
    summary = _run_loop(db_path, strategy, _finite_source(_bar(0)), broker)
    journal = TradeJournal(db_path)
    rows = journal.list_trades("run-5.2")
    journal.close()
    assert broker.get_positions() == {"SPY": 1}
    assert summary.total_trades == 1
    assert len(rows) == 1
    assert rows[0].entry_price == 101.5
    assert rows[0].qty == 1


def test_loop_closes_trade_on_sell_signal(tmp_path: Path) -> None:
    db_path = tmp_path / "trades.sqlite"
    strategy = _SequenceStrategy([Action.BUY, Action.SELL])
    broker = MockBroker(fill_price=100.0)
    summary = _run_loop(
        db_path,
        strategy,
        _finite_source(_bar(0), _bar(1)),
        broker,
    )
    journal = TradeJournal(db_path)
    row = journal.list_trades("run-5.2")[0]
    journal.close()
    assert broker.get_positions() == {"SPY": 0}
    assert row.exit_price == 100.0
    assert row.pnl == 0.0
    assert row.closed_at is not None
    assert summary.total_signals == 2
    assert summary.total_trades == 1
    assert summary.total_pnl == 0.0


def test_loop_closes_journal_during_cleanup(tmp_path: Path) -> None:
    journal = TradeJournal(tmp_path / "trades.sqlite")
    loop = LiveLoop(
        strategy=_SequenceStrategy([]),
        broker=MockBroker(),
        source=_finite_source(),
        journal=journal,
        run_id="run-5.2",
        duration=None,
    )
    asyncio.run(loop.run())
    try:
        journal.list_trades()
    except sqlite3.ProgrammingError:
        pass
    else:
        raise AssertionError("journal connection remains open")


class _DisconnectableMockBroker(MockBroker):
    """MockBroker with controllable connection state for reconnect tests."""

    def __init__(self) -> None:
        super().__init__()
        self._force_disconnected = False
        self.connect_attempts = 0

    def is_connected(self) -> bool:
        return not self._force_disconnected

    def force_disconnect(self) -> None:
        self._force_disconnected = True

    def force_reconnect(self) -> None:
        self._force_disconnected = False

    def connect(self) -> None:
        self.connect_attempts += 1
        if self._force_disconnected:
            raise ConnectionError("simulated connect failure while disconnected")


def _build_loop(
    db_path: Path,
    broker: MockBroker,
    source: MockBarSource,
    strategy: _SequenceStrategy | None = None,
    *,
    duration: timedelta | None = None,
    reconnect_config: ReconnectConfig | None = None,
    run_id: str = "run-5.3",
) -> LiveLoop:
    return LiveLoop(
        strategy=strategy or _SequenceStrategy([]),
        broker=broker,
        source=source,
        journal=TradeJournal(db_path),
        run_id=run_id,
        duration=duration,
        reconnect_config=reconnect_config,
    )


def test_reconnect_with_backoff_succeeds_after_failures(tmp_path: Path) -> None:
    broker = _DisconnectableMockBroker()
    broker.force_disconnect()
    config = ReconnectConfig(initial_delay=0.001, max_delay=0.002, max_attempts=5)
    loop = _build_loop(
        tmp_path / "trades.sqlite",
        broker,
        MockBarSource(),
        duration=None,
        reconnect_config=config,
    )

    async def reconnect_after_two_failures() -> None:
        while broker.connect_attempts < 2:
            await asyncio.sleep(0.001)
        broker.force_reconnect()

    async def driver() -> None:
        helper = asyncio.create_task(reconnect_after_two_failures())
        await loop._reconnect_with_backoff()
        await helper

    asyncio.run(driver())
    assert broker.connect_attempts == 3
    assert broker.is_connected() is True


def test_reconnect_with_backoff_raises_after_max_attempts(tmp_path: Path) -> None:
    broker = _DisconnectableMockBroker()
    broker.force_disconnect()
    config = ReconnectConfig(initial_delay=0.001, max_delay=0.002, max_attempts=3)
    loop = _build_loop(
        tmp_path / "trades.sqlite",
        broker,
        MockBarSource(),
        duration=None,
        reconnect_config=config,
    )

    async def driver() -> None:
        await loop._reconnect_with_backoff()

    with pytest.raises(ConnectionError):
        asyncio.run(driver())
    assert broker.connect_attempts == 3


def test_reconnect_with_backoff_doubles_delay_until_cap(tmp_path: Path) -> None:
    broker = _DisconnectableMockBroker()
    broker.force_disconnect()
    config = ReconnectConfig(initial_delay=1.0, max_delay=4.0, max_attempts=5)
    loop = _build_loop(
        tmp_path / "trades.sqlite",
        broker,
        MockBarSource(),
        duration=None,
        reconnect_config=config,
    )

    async def driver() -> None:
        await loop._reconnect_with_backoff()

    with pytest.raises(ConnectionError):
        asyncio.run(driver())
    assert broker.connect_attempts == 5


def test_reconnect_skipped_for_mock_broker(tmp_path: Path) -> None:
    broker = MockBroker()
    config = ReconnectConfig(initial_delay=0.001, max_delay=0.002, max_attempts=3)
    loop = _build_loop(
        tmp_path / "trades.sqlite",
        broker,
        MockBarSource(),
        duration=timedelta(milliseconds=10),
        reconnect_config=config,
    )

    asyncio.run(loop.run())

    assert broker.is_connected() is True


def test_loop_emits_daily_summary_on_clean_exit(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "trades.sqlite"
    strategy = _SequenceStrategy([])
    summary = _run_loop(
        db_path,
        strategy,
        MockBarSource(),
        duration=timedelta(milliseconds=1),
    )
    out = capsys.readouterr().out
    assert "Tageszusammenfassung" in out
    assert summary.run_id == "run-5.2"
    journal = TradeJournal(db_path)
    summaries = journal.list_summaries()
    journal.close()
    assert len(summaries) == 1
    persisted = summaries[0]
    assert persisted.run_id == "run-5.2"
    assert persisted.strategy_name == "sequence"
    assert persisted.total_trades == 0
    assert persisted.open_positions_count == 0
    assert persisted.total_pnl == 0.0
    assert persisted.duration_seconds >= 0.0
    assert isinstance(persisted.closed_at, str)


def test_loop_persists_summary_with_trade_pnl(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "trades.sqlite"
    strategy = _SequenceStrategy([Action.BUY, Action.SELL])
    broker = MockBroker(fill_price=100.0)
    _run_loop(
        db_path,
        strategy,
        _finite_source(_bar(0), _bar(1)),
        broker,
    )
    out = capsys.readouterr().out
    assert "Tageszusammenfassung" in out
    assert "Total Trades" not in out
    journal = TradeJournal(db_path)
    summaries = journal.list_summaries()
    journal.close()
    assert len(summaries) == 1
    persisted = summaries[0]
    assert persisted.total_trades == 1
    assert persisted.total_pnl == 0.0


def test_loop_emits_summary_even_when_run_interrupted(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "trades.sqlite"
    source = MockBarSource()
    source._inject(_bar(0))
    source._inject(_bar(1))

    strategy = _SequenceStrategy([Action.BUY, Action.BUY])
    loop = _build_loop(db_path, MockBroker(), source, strategy)

    async def driver() -> None:
        task = asyncio.create_task(loop.run())
        await asyncio.sleep(0.05)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(driver())

    out = capsys.readouterr().out
    assert "Tageszusammenfassung" in out
    journal = TradeJournal(db_path)
    summaries = journal.list_summaries()
    trades = journal.list_trades()
    journal.close()
    assert len(summaries) == 1
    assert summaries[0].run_id == "run-5.3"
    assert len(trades) >= 1


def test_daily_summary_dataclass_has_expected_fields() -> None:
    summary = DailySummary(
        run_id="r",
        strategy_name="s",
        total_trades=1,
        open_positions_count=0,
        total_pnl=1.5,
        duration_seconds=2.0,
        closed_at="2026-07-14T17:00:00",
    )
    assert summary.run_id == "r"
    assert summary.strategy_name == "s"
    assert summary.total_trades == 1
    assert summary.open_positions_count == 0
    assert summary.total_pnl == 1.5
    assert summary.duration_seconds == 2.0
    assert summary.closed_at == "2026-07-14T17:00:00"


def test_reconnect_config_defaults() -> None:
    config = ReconnectConfig()
    assert config.initial_delay == 1.0
    assert config.max_delay == 30.0
    assert config.max_attempts == 10
