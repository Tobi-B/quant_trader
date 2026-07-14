"""Tests for the SQLite trade journal."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from quant_trader.live import DailySummary, TradeJournal
from quant_trader.strategies import Action

_OPENED_AT = datetime(2026, 7, 14, 10, 0, 0)


def _append(journal: TradeJournal, order_id: str = "order-1", run_id: str = "run-1") -> int:
    return journal.append_open(
        run_id=run_id,
        strategy_name="sma_cross",
        ticker="SPY",
        action=Action.BUY,
        qty=2,
        price=100.0,
        client_order_id=order_id,
        opened_at=_OPENED_AT,
    )


def test_journal_creates_table_on_init(tmp_path: Path) -> None:
    db_path = tmp_path / "trades.sqlite"
    journal = TradeJournal(db_path)
    with sqlite3.connect(db_path) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'trades'"
        ).fetchone()
        index = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_trades_run_id'"
        ).fetchone()
    journal.close()
    assert table == ("trades",)
    assert index == ("idx_trades_run_id",)


def test_journal_append_open_inserts_row(tmp_path: Path) -> None:
    journal = TradeJournal(tmp_path / "trades.sqlite")
    row_id = _append(journal)
    rows = journal.list_trades()
    journal.close()
    assert row_id == 1
    assert len(rows) == 1
    assert rows[0].run_id == "run-1"
    assert rows[0].strategy_name == "sma_cross"
    assert rows[0].ticker == "SPY"
    assert rows[0].action == "BUY"
    assert rows[0].entry_price == 100.0
    assert rows[0].client_order_id == "order-1"


def test_journal_duplicate_client_order_id_raises_integrity_error(tmp_path: Path) -> None:
    journal = TradeJournal(tmp_path / "trades.sqlite")
    _append(journal)
    with pytest.raises(sqlite3.IntegrityError):
        _append(journal)
    journal.close()


def test_journal_close_trade_updates_pnl(tmp_path: Path) -> None:
    journal = TradeJournal(tmp_path / "trades.sqlite")
    _append(journal)
    closed_at = datetime(2026, 7, 14, 11, 0, 0)
    journal.close_trade("order-1", exit_price=110.0, closed_at=closed_at)
    row = journal.list_trades()[0]
    journal.close()
    assert row.exit_price == 110.0
    assert row.pnl == 20.0
    assert row.pnl_pct == pytest.approx(0.1)
    assert row.closed_at == closed_at.isoformat()


def test_journal_list_trades_filters_by_run_id(tmp_path: Path) -> None:
    journal = TradeJournal(tmp_path / "trades.sqlite")
    _append(journal, order_id="order-1", run_id="run-1")
    _append(journal, order_id="order-2", run_id="run-2")
    rows = journal.list_trades("run-2")
    journal.close()
    assert [row.client_order_id for row in rows] == ["order-2"]


def test_journal_list_trades_returns_all_in_id_order(tmp_path: Path) -> None:
    journal = TradeJournal(tmp_path / "trades.sqlite")
    _append(journal, order_id="order-1", run_id="run-1")
    _append(journal, order_id="order-2", run_id="run-2")
    rows = journal.list_trades()
    journal.close()
    assert [row.id for row in rows] == [1, 2]


def test_journal_close_releases_connection(tmp_path: Path) -> None:
    journal = TradeJournal(tmp_path / "trades.sqlite")
    journal.close()
    with pytest.raises(sqlite3.ProgrammingError):
        journal.list_trades()


def test_journal_enables_wal_mode(tmp_path: Path) -> None:
    db_path = tmp_path / "trades.sqlite"
    journal = TradeJournal(db_path)
    mode = journal._conn.execute("PRAGMA journal_mode").fetchone()[0]
    journal.close()
    assert mode == "wal"


def test_journal_creates_daily_summaries_table(tmp_path: Path) -> None:
    db_path = tmp_path / "trades.sqlite"
    journal = TradeJournal(db_path)
    with sqlite3.connect(db_path) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'daily_summaries'"
        ).fetchone()
    journal.close()
    assert table == ("daily_summaries",)


def test_journal_append_summary_inserts_row(tmp_path: Path) -> None:
    journal = TradeJournal(tmp_path / "trades.sqlite")
    summary = DailySummary(
        run_id="run-1",
        strategy_name="sma_cross",
        total_trades=5,
        open_positions_count=2,
        total_pnl=123.45,
        duration_seconds=3600.0,
        closed_at="2026-07-14T17:00:00",
    )
    row_id = journal.append_summary(summary)
    summaries = journal.list_summaries()
    journal.close()
    assert row_id == 1
    assert len(summaries) == 1
    assert summaries[0] == summary


def test_journal_list_summaries_returns_all_in_id_order(tmp_path: Path) -> None:
    journal = TradeJournal(tmp_path / "trades.sqlite")
    first = DailySummary(
        run_id="run-1",
        strategy_name="sma_cross",
        total_trades=1,
        open_positions_count=0,
        total_pnl=10.0,
        duration_seconds=60.0,
        closed_at="2026-07-14T16:00:00",
    )
    second = DailySummary(
        run_id="run-2",
        strategy_name="momentum",
        total_trades=3,
        open_positions_count=1,
        total_pnl=-5.0,
        duration_seconds=1800.0,
        closed_at="2026-07-14T17:00:00",
    )
    journal.append_summary(first)
    journal.append_summary(second)
    summaries = journal.list_summaries()
    journal.close()
    assert [s.run_id for s in summaries] == ["run-1", "run-2"]
    assert summaries[0].strategy_name == "sma_cross"
    assert summaries[1].strategy_name == "momentum"
    assert summaries[0].total_pnl == 10.0
    assert summaries[1].total_pnl == -5.0
