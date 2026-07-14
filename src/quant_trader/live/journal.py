"""SQLite-backed trade journal for live trading."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from quant_trader.strategies.types import Action


@dataclass(frozen=True)
class TradeRow:
    id: int
    run_id: str
    strategy_name: str
    ticker: str
    action: str
    qty: int
    entry_price: float | None
    exit_price: float | None
    pnl: float | None
    pnl_pct: float | None
    opened_at: str
    closed_at: str | None
    client_order_id: str
    created_at: str


class TradeJournal:
    """Persists live trades in SQLite with idempotent order identifiers."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                qty INTEGER NOT NULL,
                entry_price REAL,
                exit_price REAL,
                pnl REAL,
                pnl_pct REAL,
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                client_order_id TEXT UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_trades_run_id ON trades(run_id);
            """
        )
        self._conn.commit()

    def append_open(
        self,
        run_id: str,
        strategy_name: str,
        ticker: str,
        action: Action | str,
        qty: int,
        price: float,
        client_order_id: str,
        opened_at: datetime | str,
    ) -> int:
        action_value = action.value if isinstance(action, Action) else action
        cursor = self._conn.execute(
            """
            INSERT INTO trades (
                run_id, strategy_name, ticker, action, qty, entry_price,
                opened_at, client_order_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                strategy_name,
                ticker,
                action_value,
                qty,
                price,
                self._timestamp(opened_at),
                client_order_id,
            ),
        )
        self._conn.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return a trade row id")
        return cursor.lastrowid

    def close_trade(
        self,
        client_order_id: str,
        exit_price: float,
        closed_at: datetime | str,
    ) -> None:
        self._conn.execute(
            """
            UPDATE trades
            SET exit_price = ?,
                pnl = qty * (? - entry_price),
                pnl_pct = CASE
                    WHEN entry_price = 0 THEN NULL
                    ELSE (? - entry_price) / entry_price
                END,
                closed_at = ?
            WHERE client_order_id = ?
            """,
            (
                exit_price,
                exit_price,
                exit_price,
                self._timestamp(closed_at),
                client_order_id,
            ),
        )
        self._conn.commit()

    def list_trades(self, run_id: str | None = None) -> list[TradeRow]:
        if run_id is None:
            rows = self._conn.execute("SELECT * FROM trades ORDER BY id").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM trades WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [self._to_trade_row(row) for row in rows]

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _timestamp(value: datetime | str) -> str:
        return value.isoformat() if isinstance(value, datetime) else value

    @staticmethod
    def _to_trade_row(row: sqlite3.Row) -> TradeRow:
        return TradeRow(
            id=int(row["id"]),
            run_id=str(row["run_id"]),
            strategy_name=str(row["strategy_name"]),
            ticker=str(row["ticker"]),
            action=str(row["action"]),
            qty=int(row["qty"]),
            entry_price=None if row["entry_price"] is None else float(row["entry_price"]),
            exit_price=None if row["exit_price"] is None else float(row["exit_price"]),
            pnl=None if row["pnl"] is None else float(row["pnl"]),
            pnl_pct=None if row["pnl_pct"] is None else float(row["pnl_pct"]),
            opened_at=str(row["opened_at"]),
            closed_at=None if row["closed_at"] is None else str(row["closed_at"]),
            client_order_id=str(row["client_order_id"]),
            created_at=str(row["created_at"]),
        )


__all__ = ["TradeJournal", "TradeRow"]
