#!/usr/bin/env bash
set -e

if [ -z "$1" ] || [ "$1" = "streamlit" ]; then
  exec streamlit run scripts/backtest_dashboard.py --server.address 0.0.0.0
else
  exec "$@"
fi