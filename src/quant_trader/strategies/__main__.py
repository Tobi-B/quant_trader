"""Entry point for `python -m quant_trader.strategies`."""

from __future__ import annotations

import sys

from quant_trader.strategies.cli import main

if __name__ == "__main__":
    sys.exit(main())
