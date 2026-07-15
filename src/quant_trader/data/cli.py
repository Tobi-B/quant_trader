"""CLI entry point for fetching market data."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

from quant_trader.core.config import get_settings
from quant_trader.core.errors import TickerNotFoundError
from quant_trader.core.logging import configure_logging, get_logger
from quant_trader.core.types import Granularity
from quant_trader.data.cache import ParquetCache
from quant_trader.data.factory import build_chain
from quant_trader.data.refresh import (
    RefreshStatus,
    RefreshSummary,
    refresh_all,
    refresh_cached,
    refresh_tickers,
    refresh_universe,
)
from quant_trader.data.service import DataService
from quant_trader.universe.presets import PresetNotFoundError, PresetRepository

log = get_logger(__name__)


@dataclass(frozen=True)
class _Summary:
    ok: int
    fallback: int
    failed: int
    duration_s: float


def _build_fetch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m quant_trader.data",
        description="Marktdaten laden und in Parquet cachen.",
    )
    parser.add_argument(
        "ticker",
        nargs="?",
        help="Einzelner Ticker (z.B. SPY). Entweder ticker oder --universe.",
    )
    parser.add_argument(
        "--universe",
        help="Preset-Name (z.B. sp500, dax40, etfs). Laedt alle Ticker des Presets.",
    )
    parser.add_argument(
        "--granularity",
        default="daily",
        choices=[g.value for g in Granularity],
        help="Granularitaet (default: daily).",
    )
    parser.add_argument(
        "--start",
        help="Start-Datum (YYYY-MM-DD). Default: heute - years.",
    )
    parser.add_argument(
        "--end",
        help="End-Datum (YYYY-MM-DD). Default: heute.",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=5,
        help="Anzahl Jahre rueckwirkend, wenn --start fehlt (default: 5).",
    )
    return parser


def _build_refresh_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m quant_trader.data refresh",
        description="Cache inkrementell aktualisieren.",
    )
    parser.add_argument(
        "--tickers",
        help="Komma-getrennte Ticker-Liste (z.B. SPY,AGG).",
    )
    parser.add_argument(
        "--universe",
        help="Preset-Name (z.B. sp500, dax40, etfs).",
    )
    parser.add_argument(
        "--granularity",
        default="daily",
        choices=[g.value for g in Granularity],
        help="Granularitaet (default: daily).",
    )
    parser.add_argument(
        "--start",
        help="Start-Datum (YYYY-MM-DD). Default: heute - 10 Jahre.",
    )
    parser.add_argument(
        "--end",
        help="End-Datum (YYYY-MM-DD). Default: heute.",
    )
    return parser


def build_parser() -> argparse.ArgumentParser:
    """Return the legacy fetch parser (kept for backwards compatibility)."""
    return _build_fetch_parser()


def _is_refresh_command(argv: Sequence[str]) -> bool:
    return bool(argv) and argv[0] == "refresh"


def main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    if argv is None:
        import sys

        args_list: Sequence[str] = list(sys.argv[1:])
    else:
        args_list = list(argv)

    if _is_refresh_command(args_list):
        refresh_parser = _build_refresh_parser()
        refresh_args = refresh_parser.parse_args(args_list[1:])
        return _run_refresh(refresh_args, settings)

    fetch_parser = _build_fetch_parser()
    fetch_args = fetch_parser.parse_args(args_list)
    return _run_fetch(fetch_args, settings)


def _run_fetch(args: argparse.Namespace, settings: object) -> int:
    if not args.ticker and not args.universe:
        fetch_parser = _build_fetch_parser()
        fetch_parser.error("entweder ticker oder --universe ist erforderlich")

    tickers = _resolve_tickers(args, settings.data_dir)
    if tickers is None:
        return 1
    start, end = _resolve_dates(args)
    granularity = Granularity(args.granularity)

    cache = ParquetCache(settings.data_dir)
    chain = build_chain(settings)
    service = DataService(cache=cache, provider=chain)

    import time

    started = time.monotonic()
    ok = 0
    fallback = 0
    failed = 0
    first_ticker_not_found: str | None = None

    for ticker in tickers:
        try:
            result = service.get(ticker, start, end, granularity)
        except TickerNotFoundError as exc:
            failed += 1
            first_ticker_not_found = exc.ticker
            log.error("ticker.not_found", ticker=exc.ticker)
            break

        if result.from_cache:
            ok += 1
        elif result.used_provider == "fallback":
            ok += 1
            fallback += 1
        else:
            ok += 1

    duration = time.monotonic() - started
    summary = _Summary(ok=ok, fallback=fallback, failed=failed, duration_s=duration)
    log.info(
        "fetch.summary",
        ok=summary.ok,
        fallback=summary.fallback,
        failed=summary.failed,
        duration_s=round(summary.duration_s, 3),
    )

    if first_ticker_not_found is not None:
        log.error(
            "ticker.not_found.fail_fast",
            ticker=first_ticker_not_found,
            hint="Universe-Liste pruefen: python -m quant_trader.universe list",
        )
        return 1
    return 0


def _run_refresh(args: argparse.Namespace, settings: object) -> int:
    granularity = Granularity(args.granularity)
    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None

    cache = ParquetCache(settings.data_dir)
    chain = build_chain(settings)

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        summary = refresh_tickers(tickers, cache, chain, granularity, start=start, end=end)
    elif args.universe:
        try:
            summary = refresh_universe(args.universe, cache, chain, granularity, start=start, end=end)
        except PresetNotFoundError:
            repo = PresetRepository(settings.universe_presets_path)
            log.error(
                "universe.preset_unknown",
                preset=args.universe,
                available=repo.names(),
            )
            return 1
    else:
        summary = refresh_cached(cache, chain, granularity, start=start, end=end)

    return _exit_code_from_refresh(summary)


def _exit_code_from_refresh(summary: RefreshSummary) -> int:
    if summary.errors > 0:
        return 1
    return 0


def _resolve_tickers(args: argparse.Namespace, data_dir: Path) -> list[str] | None:
    if args.ticker:
        return [args.ticker.upper()]
    settings = get_settings()
    repo = PresetRepository(settings.universe_presets_path)
    try:
        preset = repo.get(args.universe)
    except PresetNotFoundError:
        log.error(
            "universe.preset_unknown",
            preset=args.universe,
            available=repo.names(),
        )
        return None
    return [t.upper() for t in preset.tickers]


def _resolve_dates(args: argparse.Namespace) -> tuple[date, date]:
    end = date.fromisoformat(args.end) if args.end else date.today()
    if args.start:
        start = date.fromisoformat(args.start)
    else:
        start = end - timedelta(days=365 * args.years)
    return start, end


__all__ = [
    "RefreshStatus",
    "build_parser",
    "main",
    "refresh_all",
    "refresh_cached",
    "refresh_tickers",
    "refresh_universe",
]


if __name__ == "__main__":
    sys.exit(main())
