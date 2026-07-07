# AGENTS.md

This file is read by opencode and other AI agents working on this repository.
It defines the stack, conventions, and the verification gate that **must** be honoured on every task.

## 1. Stack

- **Python**: 3.11 or 3.12 (pinned in `pyproject.toml`).
- **Package manager**: `uv`. Never use `pip install` directly; never commit `requirements.txt`.
- **Linter / formatter**: `ruff` (replaces black, isort, flake8). Config in `pyproject.toml`.
- **Tests**: `pytest`. Markers: `slow`, `live`, `integration`.
- **Type check**: `mypy --strict`. New modules must type-check.
- **Logging**: `structlog`. No `print` in `src/`.
- **Data**: Parquet cache via `pyarrow`; trade journal in SQLite.
- **Broker**: `ib_insync` (live extra).

## 2. Conventions

- **Language**: code, identifiers, commit messages and log strings in **English**.
- **Docs / CLI text / AGENTS-meta docs**: **German**.
- No inline comments. Docstrings on public classes and functions only when the name is not self-explanatory.
- No wildcard imports. No `Any` without a reason.
- Type hints on all public functions.
- Public API of a module = everything not prefixed with `_`.
- All persistence paths come from `config.settings`, never hard-coded.
- All API calls go through a `DataProvider`-style interface. No raw `requests` from strategy code.

## 3. Verification Gate (mandatory)

For each slice of work, the order **must** be:

1. **User Stories** — drafted by the agent in `docs/userstories/<phase>/<slice>.md` with INVEST, MoSCoW, T-Shirt estimate (S/M/L), and Gherkin acceptance criteria. Wait for user APPROVAL before continuing.
2. **UML diagrams** — three Mermaid diagrams (Structure, Flow, Sequence) drafted in `docs/uml/<phase>/<slice>.md` with `Status: DRAFT`. Wait for user APPROVAL.
3. **Implementation** — code only after stories + diagrams are APPROVED.
4. **Quality gates** — `make test`, `make lint`, `make smoke` (if applicable) must all be green.
5. **Commit** — small, focused Conventional Commits; one logical step per commit.

If a slice already has APPROVED diagrams stored on disk, do **not** redraft them — read them, confirm understanding, and proceed.

## 4. Memory Model

- `git log` is the primary memory across sessions. Read `git log --oneline -30` on startup.
- Persistent context lives in `docs/` and `AGENTS.md`, not in chat history.
- Keep edits small. A single phase spanning many commits is preferred over one mega-commit.

## 5. Forbidden Actions

- Do **not** invent new dependencies without checking `pyproject.toml` first.
- Do **not** create `*.md` documentation files unless they belong to a known location (`docs/`, `README.md`, `CONTRIBUTING.md`, or `docs/uml/...`).
- Do **not** update global git config. Local config in this repo only.
- Do **not** push to remote without user instruction.
- Do **not** amend, force-push, or skip hooks unless explicitly asked.
- Do **not** add `print(...)` statements; use `structlog` instead.

## 6. Standard Commands

| Command         | Purpose                                       |
|-----------------|-----------------------------------------------|
| `make install`  | `uv sync`                                     |
| `make lint`     | `ruff check` + `ruff format --check`          |
| `make format`   | `ruff format` + `ruff check --fix`            |
| `make test`     | `pytest -m "not live and not slow"`           |
| `make smoke`    | one fast end-to-end backtest                  |
| `make backtest` | `python scripts/run_backtest.py`              |
| `make data`     | `python scripts/fetch_data.py`                |
| `make clean`    | remove caches                                 |
