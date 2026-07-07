# Contributing

## Development setup

```bash
uv sync --all-extras
pre-commit install
cp .env.example .env
```

## Workflow

1. Read `AGENTS.md` for stack, conventions, and the verification gate.
2. Read `docs/00_dev_workflow.md` (German) for the practical loop.
3. For new slices: stories first (`docs/userstories/`), then UML diagrams (`docs/uml/`), then code.
4. Quality gates before commit: `make lint && make test && make smoke`.

## Commits

Conventional Commits, English:

```
feat: add momentum strategy
fix: handle missing ticker in universe loader
chore: bootstrap dev harness
docs(p1): add data layer user stories
```

One logical step per commit. Use `git log --oneline -20` to recover context.

## Branches

- `main` — always green.
- `feature/p<n>-<name>` — per-phase work, e.g. `feature/p1-data-layer`.
- PR template requires the UML diagrams to be APPROVED.

## What not to do

- Don't push without a PR.
- Don't force-push or amend public history.
- Don't commit `.env`, data, or secrets.
- Don't add new dependencies without listing them in `pyproject.toml`.