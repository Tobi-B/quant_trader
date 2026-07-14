"""Entry point for `python -m quant_trader.backtest`."""

from __future__ import annotations

import sys

from quant_trader.backtest.cli import main

if __name__ == "__main__":
    sys.exit(main())
