# QuantTrader

A quant trading app for **backtesting** and **live trading** US/EU stocks and ETFs via Interactive Brokers.

## Status

Phase 0 — development harness bootstrap. No trading code yet.

## Quickstart

```bash
uv sync --all-extras
cp .env.example .env
make lint
make test
```

## Stack

- Python 3.11 / 3.12, managed by `uv`.
- `ruff` (lint + format), `pytest` (tests), `structlog` (logging).
- Data: Alpha Vantage + yfinance fallback, Parquet cache.
- Broker: `ib_insync` (live extra).
- Dashboard: Streamlit (later).

## Project Layout

See [`docs/00_dev_workflow.md`](docs/00_dev_workflow.md) and [`AGENTS.md`](AGENTS.md).

```
src/quant_trader/    core, data, strategies, backtest, risk, live, storage
scripts/             CLI entry points (fetch_data, run_backtest, ...)
tests/               pytest test suite
docs/                German docs, user stories, UML diagrams
config/              YAML configuration
data/                Parquet cache (git-ignored)
```

## Workflow

Each phase follows:

1. User stories drafted (INVEST, MoSCoW, Gherkin).
2. UML diagrams drafted (Structure / Flow / Sequence) — Mermaid.
3. User APPROVED → implementation.
4. Quality gates: `make lint`, `make test`, `make smoke`.
5. Conventional Commits, one logical step per commit.

See `AGENTS.md` for full rules.