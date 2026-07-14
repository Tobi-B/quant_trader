"""Tests for the asynchronous live loop."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from quant_trader.core.types import Bar
from quant_trader.live import LiveLoop, MockBarSource, MockBroker, TradeJournal
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
