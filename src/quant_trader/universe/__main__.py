"""Entry point for `python -m quant_trader.universe`."""

from __future__ import annotations

import sys

from quant_trader.universe.cli import main

if __name__ == "__main__":
    sys.exit(main())
