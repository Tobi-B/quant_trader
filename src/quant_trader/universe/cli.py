"""Universe CLI entry point."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from quant_trader.core.config import get_settings
from quant_trader.core.logging import configure_logging, get_logger
from quant_trader.universe.loader import UniverseLoader
from quant_trader.universe.presets import PresetNotFoundError, PresetRepository
from quant_trader.universe.store import UniverseStore

log = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m quant_trader.universe",
        description="Universe Loader: Ticker-Listen aus Presets laden.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    load = sub.add_parser("load", help="Preset laden und als CSV speichern")
    load.add_argument("--preset", required=True, help="Name des Presets (z.B. sp500)")

    sub.add_parser("list", help="Verfuegbare und geladene Presets anzeigen")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    parser = build_parser()
    args = parser.parse_args(argv)

    presets = PresetRepository(settings.universe_presets_path)
    store = UniverseStore(settings.data_dir)
    loader = UniverseLoader(presets=presets, store=store)

    if args.command == "load":
        try:
            result = loader.load(args.preset)
        except PresetNotFoundError:
            log.error(
                "universe.preset_unknown",
                preset=args.preset,
                available=presets.names(),
            )
            return 1
        log.info(
            "universe.load.complete",
            preset=args.preset,
            written=result.written,
            skipped=result.skipped,
            path=str(result.path),
        )
        return 0

    if args.command == "list":
        available = presets.names()
        loaded = loader.list_loaded()
        log.info("universe.list.available", presets=available)
        log.info("universe.list.loaded", presets=loaded)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())