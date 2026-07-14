"""CLI entry point for `python -m quant_trader.strategies run ...`."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date, timedelta

from quant_trader.core.config import get_settings
from quant_trader.core.logging import configure_logging, get_logger
from quant_trader.core.types import Granularity
from quant_trader.data.cache import ParquetCache
from quant_trader.strategies import default_loader
from quant_trader.strategies.errors import (
    StrategyConfigError,
    StrategyError,
    UnknownStrategyError,
)
from quant_trader.strategies.runner import SignalFormatter, SignalRunner

log = get_logger(__name__)

_DEFAULT_LIMIT = 100
_DEFAULT_YEARS = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m quant_trader.strategies",
        description="Strategie auf historische Bars anwenden und Signale ausgeben.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser(
        "run",
        help="Strategie auf Cache-Bars anwenden und Signale tabellarisch ausgeben",
    )
    run.add_argument(
        "--strategy",
        required=True,
        help="Strategie-Name (z.B. sma_cross, momentum, rsi_mean_reversion, etf_rotation).",
    )
    run.add_argument(
        "--ticker",
        help="Einzelner Ticker fuer Single-Ticker-Strategien (z.B. SPY).",
    )
    run.add_argument(
        "--universe",
        help="Preset-Name (z.B. sp500, etfs) fuer Multi-Ticker-Strategien. "
        "Default: universe aus Strategie-Parametern.",
    )
    run.add_argument(
        "--granularity",
        default=Granularity.DAILY.value,
        choices=[g.value for g in Granularity],
        help="Granularitaet (default: daily).",
    )
    run.add_argument("--start", help="Start-Datum (YYYY-MM-DD). Default: heute - years.")
    run.add_argument("--end", help="End-Datum (YYYY-MM-DD). Default: heute.")
    run.add_argument(
        "--years",
        type=int,
        default=_DEFAULT_YEARS,
        help=f"Anzahl Jahre rueckwirkend, wenn --start fehlt (default: {_DEFAULT_YEARS}).",
    )
    run.add_argument(
        "--limit",
        type=int,
        default=_DEFAULT_LIMIT,
        help=f"Max. Anzahl Signal-Zeilen in der Ausgabe (default: {_DEFAULT_LIMIT}).",
    )

    sub.add_parser("list", help="Verfuegbare Strategien auflisten")
    return parser


def _resolve_dates(args: argparse.Namespace) -> tuple[date, date]:
    end = date.fromisoformat(args.end) if args.end else date.today()
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=365 * args.years)
    return start, end


def main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        names = default_loader().registered_names()
        for name in names:
            print(name)
        return 0

    if args.command != "run":
        parser.error(f"unbekanntes Kommando: {args.command}")
        return 2

    granularity = Granularity(args.granularity)
    start, end = _resolve_dates(args)
    cache = ParquetCache(settings.data_dir)
    runner = SignalRunner(cache=cache, loader=default_loader())
    formatter = SignalFormatter()

    try:
        signals = runner.run(
            args.strategy,
            ticker=args.ticker or "",
            universe=args.universe,
            start=start,
            end=end,
            granularity=granularity,
        )
    except UnknownStrategyError as exc:
        log.error(
            "signal_runner.unknown_strategy",
            strategy=exc.name,
            available=exc.available,
        )
        return 1
    except StrategyConfigError as exc:
        log.error("signal_runner.config_error", message=str(exc))
        return 1
    except FileNotFoundError as exc:
        log.error("signal_runner.cache_missing", message=str(exc))
        return 1
    except StrategyError as exc:
        log.error("signal_runner.strategy_error", message=str(exc))
        return 1

    print(formatter.format_signals(signals, limit=args.limit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
