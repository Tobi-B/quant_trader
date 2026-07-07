"""Backtest entry point placeholder (Phase 3)."""

from __future__ import annotations

from quant_trader.core.logging import configure_logging, get_logger

log = get_logger(__name__)


def main() -> None:
    configure_logging("INFO")
    log.info("backtest.not_implemented", phase=3, slice="engine")


if __name__ == "__main__":
    main()