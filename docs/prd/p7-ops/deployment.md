# PRD: Slice 7.1 - Docker-Deployment + CI/CD

Phase:    P7 Docker-Deployment
Slice:    7.1 Docker-Deployment (Dockerfile + Compose + CI/CD) (1 grosser Slice)
Status:   DRAFT  (User "weiter mit naechstem slice" gilt als implizite Approval; UML auf APPROVED setzen)
Author:   opencode
Created:  2026-07-14
Updated:  2026-07-14

## Goal

Ein produktionsreifes Docker-Image fuer das gesamte QuantTrader-Projekt
(Streamlit-Dashboard + CLI) plus eine docker-compose-Konfiguration
fuer lokales Testen plus eine GitHub-Actions-CI fuer automatische
Verifikation. Damit ist das Projekt reproduzierbar deployable.

## Scope (IN)

- `Dockerfile` (NEU, ~30 Zeilen, Multi-Stage):
  - `FROM python:3.12-slim AS builder`
  - `RUN pip install uv && uv pip install --system ".[ui,dev]"`
  - `FROM python:3.12-slim AS runtime`
  - `COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages`
  - `COPY src/ scripts/ pyproject.toml /app/`
  - `WORKDIR /app`
  - `EXPOSE 8501`
  - `ENTRYPOINT ["/app/scripts/entrypoint.sh"]`
  - `CMD ["streamlit", "run", "scripts/backtest_dashboard.py", "--server.address", "0.0.0.0"]`
- `.dockerignore` (NEU, ~25 Zeilen):
  - Schliesst aus: `.venv/`, `__pycache__/`, `.pytest_cache/`,
    `.mypy_cache/`, `.ruff_cache/`, `data/`, `reports/`, `*.pyc`,
    `*.pyo`, `*.egg-info/`, `.git/`, `.github/`, `tests/`, `.env`,
    `*.sqlite`, `*.sqlite-journal`, `*.sqlite-wal`, `docs/`, `*.md`,
    `Makefile`, `scripts/fetch_data.py` (oder behalten, ist egal)
- `docker-compose.yml` (NEU, ~25 Zeilen):
  - Service `qtrader` mit `build: .`
  - `container_name: quant-trader`
  - `env_file: .env`
  - `volumes: ./data:/app/data, ./reports:/app/reports, ./quant_trader.sqlite:/app/quant_trader.sqlite`
  - `ports: "8501:8501"`
  - `stdin_open: true`, `tty: true`
  - `command: ["streamlit", "run", "scripts/backtest_dashboard.py", "--server.address", "0.0.0.0"]`
- `scripts/entrypoint.sh` (NEU, ~10 Zeilen):
  - `#!/usr/bin/env bash`, `set -e`
  - Akzeptiert CLI-Args; default Streamlit
- `.github/workflows/ci.yml` (NEU, ~40 Zeilen):
  - Trigger: `push` und `pull_request` zu `main`
  - `jobs.test`: checkout, setup-python (3.12), pip install uv,
    `uv sync --all-extras`, `uv run ruff check src tests`,
    `uv run ruff format --check src tests`, `uv run mypy src`,
    `uv run pytest -m "not live and not slow"`
  - `jobs.docker` (needs test): `docker build .` (kein Push, nur
    Verifikation dass Build erfolgreich)
- `docs/SECURITY.md` (aendern): hinzufuegen, dass `.env` niemals
  ins Image committet wird (NFR-Sec-1)
- Tests: `tests/ops/` (NEU, gesamt mind. 5 Tests):
  - `test_dockerfile.py` (mind. 2 Tests):
    - `test_dockerfile_exists_and_has_multistage` (parst Dockerfile,
      prueft dass "AS builder" und "AS runtime" enthalten sind)
    - `test_dockerfile_exposes_8501` (parst Dockerfile, prueft EXPOSE)
  - `test_dockerignore.py` (mind. 1 Test):
    - `test_dockerignore_excludes_venv_and_cache`
  - `test_compose.py` (mind. 1 Test):
    - `test_compose_file_is_valid_yaml_and_has_qtrader_service`
  - `test_ci_workflow.py` (mind. 1 Test):
    - `test_ci_workflow_yaml_has_lint_test_docker_jobs`
  - Verwende `pathlib.Path` + `yaml.safe_load` + Regex
- Doku-Updates:
  - `docs/STATE.md`: Slice 7.1 auf DONE, Tag `p7-ops/7.1`
  - "Was steht"-Sektion: Docker-Image, docker-compose, CI-Workflow
  - "Was offen"-Sektion: leer (Projekt funktional + deployable)
  - `docs/adr/0014-docker-deployment-architecture.md`: Status `proposed` -> `accepted`
  - `docs/requirements/nfrs.md`: NFR-Ops-1 auf `APPROVED`

## Out of Scope (verbindlich)

- Production-Deployment (Cloud-Run, Kubernetes, Helm)
- Secrets-Management (Vault, K8s-Secrets)
- HTTPS/Reverse-Proxy (Traefik, nginx, Let's Encrypt)
- Auto-Image-Push zu Docker Hub / GHCR (manuelles `docker build`
  reicht; CI verifiziert nur den Build)
- DB-Backup-Strategie
- Monitoring/Prometheus/Grafana
- Health-Checks
- Resource-Limits (CPU/Memory) im Container
- Multi-Arch-Builds (ARM64)
- Non-Root-User im Container (YAGNI fuer persoenlichen Use-Case)
- Pre-built wheels
- Auto-Restart bei Container-Crash
- Phase 8+ (Cloud-Deployment)

## Constraints

- AGENTS.md-Regeln gelten automatisch.
- Keine neuen Dependencies.
- Kein `print`, kein globaler State.
- Code englisch, Doku deutsch (wie immer).
- Type-Hints auf allen Public-Funktionen (mypy --strict).
- **KRITISCH**: alle 434 bestehenden Tests unveraendert gruen
- Dockerfile multi-stage (builder + runtime) fuer kleines finales Image
- Image-Groesse-Ziel: < 500 MB
- CI laeuft bei push und PR zu main
- CI verifiziert Build, pusht KEIN Image zu Registry
- Backward-Compat: 434 bestehende Tests unveraendert gruen

## Mapped NFRs

- NFR-Ops-1 (Lokale Entwicklung + spaeteres Docker-Deployment)
- NFR-Sec-1 (API-Keys via .env, niemals im Repo/Image)
- NFR-Obs-1 (CI-Logs via GitHub Actions, strukturiert)

## UML-Referenz

Visualisiert in: `docs/uml/p7-ops/deployment.md` (Status: wird auf
APPROVED gesetzt mit diesem Slice).

## Done when

- [ ] `Dockerfile` mit Multi-Stage-Build
- [ ] `.dockerignore` schliesst Caches, .venv, data, reports, .git, .env aus
- [ ] `docker-compose.yml` mit App-Service + Volumes
- [ ] `scripts/entrypoint.sh` mit CLI-Args-Handling
- [ ] `.github/workflows/ci.yml` mit lint, test, mypy, docker build
- [ ] Tests in `tests/ops/` mit gesamt mind. 5 Tests
- [ ] `make test` gruen (alle 434 alten + neuen Tests)
- [ ] `make lint` gruen
- [ ] `mypy --strict` gruen (0 errors)
- [ ] NFR-Ops-1 auf APPROVED
- [ ] ADR-0014 auf "accepted"
- [ ] Conventional Commit `feat(p7-ops): slice 7.1 docker deployment`
- [ ] `docs/STATE.md` aktualisiert: Slice 7.1 auf DONE, Tag `p7-ops/7.1`
- [ ] Phase 7 DONE, "Was offen"-Sektion leer

## Anti-Drift-Reminder

Vor dem Coden:
```
git log --oneline -10
cat docs/STATE.md
cat docs/userstories/p7-ops/deployment.md
cat docs/adr/0014-docker-deployment-architecture.md
cat docs/uml/p7-ops/deployment.md
cat docs/prd/p7-ops/deployment.md
```

Waehrend des Codens:
- Tue **nur** das, was in `Scope (IN)` steht. Production-Hardening,
  Cloud-Deployment, etc. sind out.
- **KRITISCH**: alle 434 bestehenden Tests unveraendert gruen.

Nach dem Coden:
- Conventional Commit mit `feat(p7-ops): slice 7.1 docker deployment`.
- Commit-Body: warum Multi-Stage (Image-Groesse), warum keine
  Auto-Push zu Registry (manuelles docker build reicht).
