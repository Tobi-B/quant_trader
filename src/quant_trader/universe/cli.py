"""Universe CLI entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import timedelta

from quant_trader.core.config import Settings, get_settings
from quant_trader.core.errors import (
    CatalogRefreshError,
    CatalogUnavailableError,
    EmptyUniverseSelectionError,
)
from quant_trader.core.logging import configure_logging, get_logger
from quant_trader.data.instrument_catalog import (
    InstrumentCatalogService,
    InstrumentCatalogSnapshotStore,
)
from quant_trader.data.public_catalog import PublicCatalogProvider
from quant_trader.universe.dynamic_store import DynamicUniverseStore, UniverseAlreadyExistsError
from quant_trader.universe.loader import UniverseLoader
from quant_trader.universe.presets import PresetNotFoundError, PresetRepository
from quant_trader.universe.store import UniverseStore

log = get_logger(__name__)


def _build_catalog_service() -> InstrumentCatalogService:
    settings = get_settings()
    return InstrumentCatalogService(
        PublicCatalogProvider(),
        InstrumentCatalogSnapshotStore(settings.catalog_path),
        DynamicUniverseStore(settings.dynamic_universes_path),
        refresh_interval=timedelta(hours=settings.catalog_max_age_hours),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m quant_trader.universe",
        description="Universe Loader: Ticker-Listen aus Presets laden.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    load = sub.add_parser("load", help="Preset laden und als CSV speichern")
    load.add_argument("--preset", required=True, help="Name des Presets (z.B. sp500)")

    sub.add_parser("list", help="Verfuegbare und geladene Presets anzeigen")

    catalog = sub.add_parser("catalog", help="Zentralen Instrumentkatalog verwalten")
    catalog_sub = catalog.add_subparsers(dest="catalog_command", required=True)

    catalog_refresh = catalog_sub.add_parser("refresh", help="Katalog von FMP aktualisieren")
    catalog_refresh.add_argument(
        "--force", action="store_true", help="Aktualisierung erzwingen, auch wenn noch frisch"
    )

    catalog_sub.add_parser("status", help="Snapshot-Alter und Instrumentanzahl anzeigen")

    catalog_list = catalog_sub.add_parser("list", help="Instrumente im Katalog durchsuchen")
    catalog_list.add_argument("--query", default="", help="Suchbegriff (Symbol oder Name)")
    catalog_list.add_argument("--type", dest="instrument_type", help="Filter: Instrumentart")
    catalog_list.add_argument("--limit", type=int, default=20, help="Max. Anzahl Treffer")

    universe = sub.add_parser("universe", help="Dynamische Universen verwalten")
    universe_sub = universe.add_subparsers(dest="universe_command", required=True)

    universe_save = universe_sub.add_parser(
        "save", help="Katalog-Filter als benanntes Universe speichern"
    )
    universe_save.add_argument("--name", required=True, help="Name des neuen Universe")
    universe_save.add_argument("--query", default="", help="Suchbegriff (Symbol oder Name)")
    universe_save.add_argument("--type", dest="instrument_type", help="Filter: Instrumentart")
    universe_save.add_argument("--country", help="Filter: Land")
    universe_save.add_argument("--exchange", help="Filter: Boerse")
    universe_save.add_argument("--sector", help="Filter: Sektor")
    universe_save.add_argument(
        "--overwrite", action="store_true", help="Bestehendes Universe ueberschreiben"
    )

    universe_sub.add_parser("list", help="Gespeicherte dynamische Universen anzeigen")

    universe_load = universe_sub.add_parser("load", help="Ticker eines Universe anzeigen")
    universe_load.add_argument("--name", required=True, help="Name des Universe")

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

    if args.command == "catalog":
        return _run_catalog_command(args)

    if args.command == "universe":
        return _run_universe_command(args, settings)

    return 0


def _run_catalog_command(args: argparse.Namespace) -> int:
    service = _build_catalog_service()

    if args.catalog_command == "refresh":
        try:
            result = service.refresh(force=args.force)
        except CatalogUnavailableError as exc:
            log.error("catalog.cli.unavailable", reason=exc.reason)
            return 1
        except CatalogRefreshError as exc:
            log.error("catalog.cli.refresh_error", provider=exc.provider, reason=exc.reason)
            return 1
        log.info(
            "catalog.cli.refresh.complete",
            total=result.total,
            added=result.added,
            removed=result.removed,
            used_fallback=result.used_fallback,
        )
        return 0

    if args.catalog_command == "status":
        status = service.snapshot_status()
        log.info(
            "catalog.cli.status",
            snapshot_id=status.snapshot_id,
            total=status.total,
            age_hours=None if status.age is None else round(status.age.total_seconds() / 3600, 1),
            needs_refresh=status.needs_refresh,
        )
        return 0

    if args.catalog_command == "list":
        try:
            results = service.search(
                args.query, limit=args.limit, instrument_type=args.instrument_type
            )
        except CatalogUnavailableError as exc:
            log.error("catalog.cli.unavailable", reason=exc.reason)
            return 1
        log.info(
            "catalog.cli.list",
            count=len(results),
            tickers=[i.ticker for i in results],
        )
        return 0

    return 0


def _run_universe_command(args: argparse.Namespace, settings: Settings) -> int:
    dynamic_store = DynamicUniverseStore(settings.dynamic_universes_path)

    if args.universe_command == "save":
        service = _build_catalog_service()
        filters = {
            key: value
            for key, value in {
                "instrument_type": args.instrument_type,
                "country": args.country,
                "exchange": args.exchange,
                "sector": args.sector,
            }.items()
            if value
        }
        try:
            universe = service.build_dynamic_universe(args.name, filters=filters, query=args.query)
        except EmptyUniverseSelectionError:
            log.error("universe.cli.empty_selection", name=args.name)
            return 1
        except CatalogUnavailableError as exc:
            log.error("catalog.cli.unavailable", reason=exc.reason)
            return 1
        try:
            path = dynamic_store.save(universe, overwrite=args.overwrite)
        except UniverseAlreadyExistsError:
            log.error("universe.cli.already_exists", name=args.name)
            return 1
        log.info(
            "universe.cli.save.complete",
            name=universe.name,
            tickers=len(universe.tickers),
            path=str(path),
        )
        return 0

    if args.universe_command == "list":
        log.info("universe.cli.dynamic_list", names=dynamic_store.list_loaded())
        return 0

    if args.universe_command == "load":
        try:
            universe = dynamic_store.load(args.name)
        except FileNotFoundError:
            log.error("universe.cli.not_found", name=args.name)
            return 1
        log.info(
            "universe.cli.load.complete",
            name=universe.name,
            tickers=list(universe.tickers),
        )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
