"""Backtest CLI: `python -m quant_trader.backtest {run,list}`.

The CLI parses user arguments, wires up a `BacktestOrchestrator` (run) or
`ReportLoader` (list), and prints results to the console. Errors are
translated into a single `int` exit code (0 = success, 1 = user error,
2 = argparse usage error). All logs are structured (structlog); the
console output uses the `ConsoleFormatter` from the report package.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import NoReturn

from quant_trader.backtest.errors import (
    BacktestError,
    CacheMissingError,
    InvalidParamsError,
    UnknownStrategyError,
)
from quant_trader.backtest.metrics import MetricsCalculator
from quant_trader.backtest.orchestrator import BacktestOrchestrator
from quant_trader.backtest.report.console import ConsoleFormatter
from quant_trader.backtest.report.loader import ReportLoader
from quant_trader.backtest.types import FillMode
from quant_trader.core.config import get_settings
from quant_trader.core.logging import configure_logging, get_logger
from quant_trader.core.types import Granularity
from quant_trader.data.cache import ParquetCache
from quant_trader.strategies import default_loader

log = get_logger(__name__)

_DEFAULT_INITIAL_CASH = 100_000.0
_DEFAULT_REPORTS_DIR = "./reports"


class _HelpOnErrorParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        sys.stderr.write(f"Fehler: {message}\n")
        self.print_help(sys.stderr)
        sys.exit(2)


def build_parser() -> argparse.ArgumentParser:
    parser = _HelpOnErrorParser(
        prog="python -m quant_trader.backtest",
        description=(
            "Backtest starten oder vergangene Runs auflisten. "
            "Strategie + Bars aus dem Cache, Report unter reports/<run-id>/."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser(
        "run",
        help="Backtest starten (Strategie + Ticker/Universe + Zeitraum)",
    )
    run.add_argument(
        "--strategy",
        required=True,
        help="Strategie-Name (z.B. sma_cross, etf_rotation).",
    )
    run.add_argument(
        "--ticker",
        default="",
        help="Einzelner Ticker fuer Single-Ticker-Strategien (z.B. SPY).",
    )
    run.add_argument(
        "--universe",
        default=None,
        help="Preset-Name (z.B. sp500, etfs) fuer Multi-Ticker-Strategien. "
        "Default: universe aus Strategie-Parametern.",
    )
    run.add_argument(
        "--start",
        required=True,
        help="Start-Datum (YYYY-MM-DD).",
    )
    run.add_argument(
        "--end",
        required=True,
        help="End-Datum (YYYY-MM-DD).",
    )
    run.add_argument(
        "--granularity",
        default=Granularity.DAILY.value,
        choices=[g.value for g in Granularity],
        help="Granularitaet (default: daily).",
    )
    run.add_argument(
        "--fill-mode",
        default=FillMode.NEXT_OPEN.value,
        choices=[m.value for m in FillMode],
        help="Fill-Modus (default: next_open).",
    )
    run.add_argument(
        "--initial-cash",
        type=float,
        default=_DEFAULT_INITIAL_CASH,
        help=f"Startkapital in USD (default: {_DEFAULT_INITIAL_CASH:g}).",
    )
    run.add_argument(
        "--no-report",
        action="store_true",
        help="Keine HTML/JSON-Dateien unter reports/ schreiben.",
    )
    run.add_argument(
        "--reports-dir",
        default=_DEFAULT_REPORTS_DIR,
        help=f"Ziel-Verzeichnis fuer Reports (default: {_DEFAULT_REPORTS_DIR}).",
    )

    list_parser = sub.add_parser(
        "list",
        help="Alle bisherigen Backtests aus reports/ auflisten",
    )
    list_parser.add_argument(
        "--reports-dir",
        default=_DEFAULT_REPORTS_DIR,
        help=f"Quell-Verzeichnis fuer Reports (default: {_DEFAULT_REPORTS_DIR}).",
    )
    return parser


def _format_run_list(summaries: Sequence[object]) -> str:
    if not summaries:
        return "Noch keine Backtests gelaufen."
    headers = ("RUN_ID", "STRATEGIE", "START", "END", "FINAL_EQUITY", "SHARPE")
    rows: list[tuple[str, ...]] = []
    for s in summaries:
        run_id = str(getattr(s, "run_id", ""))
        strategy = str(getattr(s, "strategy_name", ""))
        start = getattr(s, "start", None)
        end = getattr(s, "end", None)
        final_equity = getattr(s, "final_equity", 0.0)
        sharpe = getattr(s, "sharpe", None)
        rows.append(
            (
                run_id,
                strategy,
                start.isoformat() if start else "-",
                end.isoformat() if end else "-",
                f"{float(final_equity):,.2f}",
                "n/a" if sharpe is None else f"{float(sharpe):.4f}",
            )
        )
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(c)) for w, c in zip(widths, row, strict=False)]
    sep = "-+-".join("-" * w for w in widths)
    lines: list[str] = [
        " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)),
        sep,
    ]
    for row in rows:
        lines.append(" | ".join(c.ljust(widths[i]) for i, c in enumerate(row)))
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        reports_dir = Path(getattr(args, "reports_dir", _DEFAULT_REPORTS_DIR))
        loader = ReportLoader(reports_dir)
        summaries = loader.list_runs()
        print(_format_run_list(summaries))
        return 0

    if args.command != "run":
        parser.error(f"unbekanntes Kommando: {args.command}")
        return 2

    try:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
    except ValueError as exc:
        log.error("backtest.cli.invalid_date", message=str(exc))
        print(
            f"Fehler: ungueltiges Datum ({exc}). Erwartet Format YYYY-MM-DD.",
            file=sys.stderr,
        )
        return 1

    granularity = Granularity(args.granularity)
    fill_mode = FillMode(args.fill_mode)
    cache = ParquetCache(settings.data_dir)
    reports_dir = Path(getattr(args, "reports_dir", _DEFAULT_REPORTS_DIR))
    orchestrator = BacktestOrchestrator(
        cache=cache,
        loader=default_loader(),
        reports_dir=reports_dir,
    )

    run_id = f"{args.strategy}-{start.isoformat()}-{end.isoformat()}"
    metrics_calc = MetricsCalculator()
    formatter = ConsoleFormatter()

    try:
        result = orchestrator.run(
            run_id,
            strategy_name=args.strategy,
            ticker=args.ticker or "",
            universe=args.universe,
            start=start,
            end=end,
            granularity=granularity,
            fill_mode=fill_mode,
            initial_cash=args.initial_cash,
            write_report=not args.no_report,
        )
    except UnknownStrategyError as exc:
        available = ", ".join(exc.available) if exc.available else "(keine)"
        print(
            f"Fehler: unbekannte Strategie '{exc.name}'. Verfuegbar: {available}",
            file=sys.stderr,
        )
        return 1
    except CacheMissingError as exc:
        print(
            f"Fehler: {exc}\nTipp: `python -m quant_trader.data {exc.ticker}` aufrufen.",
            file=sys.stderr,
        )
        return 1
    except InvalidParamsError as exc:
        print(f"Fehler: ungueltige Parameter - {exc}", file=sys.stderr)
        return 1
    except BacktestError as exc:
        print(f"Fehler: Backtest fehlgeschlagen - {exc}", file=sys.stderr)
        return 1

    metrics = metrics_calc.calculate(result)
    print(formatter.format_report(result, metrics, top=10))
    return 0


if __name__ == "__main__":
    sys.exit(main())
