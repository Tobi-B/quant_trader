"""Data fetch entry point placeholder (Phase 1)."""

from __future__ import annotations

from quant_trader.core.logging import configure_logging, get_logger

log = get_logger(__name__)


def main() -> None:
    configure_logging("INFO")
    log.info("fetch.not_implemented", phase=1, slice="data-layer")


if __name__ == "__main__":
    main()