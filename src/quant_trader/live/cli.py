"""Live trading CLI for running strategies and listing journal trades."""

from __future__ import annotations

import argparse
import asyncio
import re
import uuid
from collections.abc import Sequence
from datetime import timedelta

from quant_trader.core.config import Settings, get_settings
from quant_trader.core.logging import configure_logging, get_logger
from quant_trader.live.bars import IBKRBarSource, MockBarSource, RealtimeBarSource
from quant_trader.live.factory import build_broker
from quant_trader.live.journal import TradeJournal
from quant_trader.live.loop import LiveLoop
from quant_trader.live.protocol import BrokerClient
from quant_trader.strategies import default_loader
from quant_trader.strategies.base import StrategyBase

_logger = get_logger("live.cli")
_DURATION_PATTERN = re.compile(r"^(?P<value>\d+(?:\.\d+)?)(?P<unit>[smh])$")


def _parse_duration(value: str) -> timedelta:
    match = _DURATION_PATTERN.fullmatch(value.lower())
    if match is None:
        raise argparse.ArgumentTypeError("Dauer muss z.B. 30s, 10m oder 1h sein.")
    amount = float(match.group("value"))
    if amount <= 0:
        raise argparse.ArgumentTypeError("Dauer muss groesser als null sein.")
    factors = {"s": 1.0, "m": 60.0, "h": 3600.0}
    return timedelta(seconds=amount * factors[match.group("unit")])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m quant_trader.live",
        description="Live-Trading starten oder gespeicherte Trades auflisten.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Eine Strategie im Live-Loop starten")
    run.add_argument("--strategy", required=True, help="Name der registrierten Strategie.")
    run.add_argument("--ticker", required=True, help="Ticker, z.B. SPY.")
    run.add_argument(
        "--broker",
        choices=("mock", "ibkr"),
        default="mock",
        help="Broker-Auswahl (default: mock).",
    )
    run.add_argument(
        "--duration",
        type=_parse_duration,
        default=None,
        help="Optionale Laufzeit, z.B. 30s, 10m oder 1h.",
    )
    list_parser = subparsers.add_parser("list", help="Trades aus dem Journal auflisten")
    list_parser.add_argument("--run-id", default=None, help="Optional nach Run-ID filtern.")
    return parser


def _source_for(broker_name: str, broker: BrokerClient) -> RealtimeBarSource:
    if broker_name == "mock":
        return MockBarSource()
    from quant_trader.live.ibkr import IBKRBroker

    if not isinstance(broker, IBKRBroker):
        raise RuntimeError("IBKR-Broker konnte nicht erstellt werden.")
    return IBKRBarSource(broker.ib_client)


def _list_trades(settings: Settings, run_id: str | None) -> int:
    journal = TradeJournal(settings.db_path)
    try:
        trades = journal.list_trades(run_id)
        if not trades:
            _logger.info("live.cli.no_trades", message="Keine Trades gefunden.")
            return 0
        for trade in trades:
            _logger.info(
                "live.cli.trade",
                id=trade.id,
                run_id=trade.run_id,
                strategy=trade.strategy_name,
                ticker=trade.ticker,
                action=trade.action,
                qty=trade.qty,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                pnl=trade.pnl,
                opened_at=trade.opened_at,
                closed_at=trade.closed_at,
            )
        return 0
    finally:
        journal.close()


def main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    args = build_parser().parse_args(argv)
    if args.command == "list":
        try:
            return _list_trades(settings, args.run_id)
        except Exception as exc:
            _logger.error("live.cli.list_failed", error=str(exc))
            return 1

    try:
        run_settings = settings.model_copy(
            update={"live_enabled": args.broker == "ibkr"},
        )
        broker = build_broker(run_settings)
        source = _source_for(args.broker, broker)
        strategy = default_loader().load(args.strategy, ticker=args.ticker.upper())
        if not isinstance(strategy, StrategyBase):
            raise ValueError("Live-Trading unterstuetzt nur Einzel-Ticker-Strategien.")
        journal = TradeJournal(settings.db_path)
        loop = LiveLoop(
            strategy=strategy,
            broker=broker,
            source=source,
            journal=journal,
            run_id=str(uuid.uuid4()),
            duration=args.duration,
        )
        summary = asyncio.run(loop.run())
    except KeyboardInterrupt:
        _logger.info("live.cli.interrupted")
        return 0
    except SystemExit as exc:
        _logger.error("live.cli.dependency_missing", error=str(exc))
        return 1
    except Exception as exc:
        _logger.error("live.cli.run_failed", error=str(exc))
        return 1
    _logger.info(
        "live.cli.run_complete",
        run_id=summary.run_id,
        total_signals=summary.total_signals,
        total_trades=summary.total_trades,
        total_pnl=summary.total_pnl,
    )
    return 0


__all__ = ["build_parser", "main"]
