"""Tests for the live trading CLI."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from quant_trader.core.config import Settings
from quant_trader.live import TradeJournal
from quant_trader.live.cli import build_parser, main
from quant_trader.strategies import Action


def test_parser_run_minimal() -> None:
    args = build_parser().parse_args(["run", "--strategy", "sma_cross", "--ticker", "SPY"])
    assert args.command == "run"
    assert args.strategy == "sma_cross"
    assert args.ticker == "SPY"
    assert args.broker == "mock"
    assert args.duration is None


def test_parser_run_parses_broker_and_duration() -> None:
    args = build_parser().parse_args(
        [
            "run",
            "--strategy",
            "sma_cross",
            "--ticker",
            "SPY",
            "--broker",
            "ibkr",
            "--duration",
            "1h",
        ]
    )
    assert args.broker == "ibkr"
    assert args.duration == timedelta(hours=1)


def test_parser_list_accepts_run_id() -> None:
    args = build_parser().parse_args(["list", "--run-id", "run-1"])
    assert args.command == "list"
    assert args.run_id == "run-1"


def test_parser_rejects_invalid_duration() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "run",
                "--strategy",
                "sma_cross",
                "--ticker",
                "SPY",
                "--duration",
                "forever",
            ]
        )


def test_cli_list_returns_zero_and_logs_trade(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "trades.sqlite"
    journal = TradeJournal(db_path)
    journal.append_open(
        run_id="run-1",
        strategy_name="sma_cross",
        ticker="SPY",
        action=Action.BUY,
        qty=1,
        price=100.0,
        client_order_id="order-1",
        opened_at=datetime(2026, 7, 14, 10, 0, 0),
    )
    journal.close()
    logger = MagicMock()
    monkeypatch.setattr("quant_trader.live.cli.get_settings", lambda: Settings(db_path=db_path))
    monkeypatch.setattr("quant_trader.live.cli._logger", logger)
    rc = main(["list", "--run-id", "run-1"])
    assert rc == 0
    logger.info.assert_called_once()
