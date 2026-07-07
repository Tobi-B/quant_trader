PYTHON ?= python
UV ?= uv
ACT ?= act

.PHONY: help install lint format test smoke backtest data clean uml-check

help:
	@echo "Targets: install lint format test smoke backtest data clean uml-check"

install:
	$(UV) sync --all-extras

lint:
	$(UV) run ruff check src tests
	$(UV) run ruff format --check src tests

format:
	$(UV) run ruff format src tests
	$(UV) run ruff check --fix src tests

test:
	$(UV) run pytest -m "not live and not slow"

smoke:
	$(UV) run python scripts/run_backtest.py \
		--strategy sma_cross --ticker SPY \
		--start 2023-01-01 --end 2023-06-30

backtest:
	$(UV) run python scripts/run_backtest.py $(ARGS)

data:
	$(UV) run python scripts/fetch_data.py $(TICKER)

uml-check:
	@if command -v mmdc >/dev/null 2>&1; then \
		find docs/uml -name "*.md" -print0 | xargs -0 -I{} sh -c 'mmdc -i "{}" -o /tmp/_uml_check.svg >/dev/null 2>&1 || echo "Mermaid syntax issue in {}"'; \
	else \
		echo "mmdc (mermaid-cli) not installed - skipping"; \
	fi

clean:
	@$(UV) run python -c "import shutil, os; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache','.ruff_cache','.mypy_cache','htmlcov']]"
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true