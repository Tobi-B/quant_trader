"""CLI entry point."""

from __future__ import annotations

from quant_trader.core.logging import configure_logging, get_logger

log = get_logger(__name__)


def main() -> None:
    configure_logging("INFO")
    log.info("cli.started", note="QuantTrader CLI placeholder - Phase 0 bootstrap")
    log.info("cli.hint", next_step="Phase 1: Datenlayer folgt")
