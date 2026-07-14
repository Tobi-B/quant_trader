# ADR 0014: Docker-Deployment-Architektur (Multi-Stage + Compose + CI)

Status:     proposed
Datum:      2026-07-14
Phase:      P7 Docker-Deployment
Supersedes: -
Superseded by: -

## Context

Phase 1-5 sind abgeschlossen (Phase 6 (Risk) ebenfalls). Das Projekt
ist funktional komplett, aber noch nicht deployable. Phase 7 (Docker-
Deployment) soll:
1. Ein reproduzierbares Docker-Image fuer das gesamte Projekt liefern
2. Lokales Testen via `docker compose up` ermoeglichen
3. CI-Build via GitHub Actions sicherstellen

Im Repo vorhanden:
- 434 Tests gruen (alle Phasen 1-5)
- `pyproject.toml` mit `ui` extra (streamlit) und `live` extra (ib_insync)
- `scripts/backtest_dashboard.py` (Streamlit-Entry-Point)
- `scripts/fetch_data.py`, `scripts/run_backtest.py` (CLI-Entry-Points)
- `Makefile` (install, lint, test, smoke, backtest, data, clean)

## Decision

### 1. `Dockerfile` (Multi-Stage)

**Builder-Stage** (`python:3.12-slim AS builder`):
- `uv pip install --system --extra ui --extra dev` (alle Extras)
  - HINWEIS: `--extra ui` und `--extra dev` werden gebraucht fuer
    Streamlit + Tests; Production-Container braucht nicht `dev`
- COPY source code
- Optional: pre-compile wheels

**Runtime-Stage** (`python:3.12-slim AS runtime`):
- COPY nur `src/`, `scripts/`, `pyproject.toml`, `README.md`
- COPY `--from=builder` installierte Packages
- Working dir `/app`
- `ENTRYPOINT ["/app/scripts/entrypoint.sh"]`
- `EXPOSE 8501` (Streamlit default)
- `CMD ["streamlit", "run", "scripts/backtest_dashboard.py", "--server.address", "0.0.0.0"]`

Image-Groesse-Ziel: < 500 MB.

### 2. `.dockerignore`

Ausschliessen:
- `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- `data/`, `reports/` (werden via Volumes gemountet)
- `*.pyc`, `*.pyo`, `*.egg-info/`
- `.git/`, `.github/` (CI separat, nicht im Image noetig)
- `tests/` (Test-Code nicht im Production-Image)
- `.env` (Secrets via env_file mount, nicht im Image)
- `*.sqlite`, `*.sqlite-journal`, `*.sqlite-wal`
- `docs/`, `*.md` (nur Source-Code im Image)
- `Makefile` (nicht im Container noetig)

### 3. `docker-compose.yml`

```yaml
version: "3.9"
services:
  qtrader:
    build: .
    container_name: quant-trader
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./reports:/app/reports
      - ./quant_trader.sqlite:/app/quant_trader.sqlite
    ports:
      - "8501:8501"
    stdin_open: true
    tty: true
    command: ["streamlit", "run", "scripts/backtest_dashboard.py", "--server.address", "0.0.0.0"]
```

Volumes:
- `./data:/app/data` (Parquet-Cache persistent)
- `./reports:/app/reports` (Backtest-Reports persistent)
- `./quant_trader.sqlite:/app/quant_trader.sqlite` (Trade-Journal persistent)
- `env_file: .env` (API-Keys)
- `stdin_open + tty` fuer interaktive CLI (`docker compose exec ...`)

### 4. `scripts/entrypoint.sh`

```bash
#!/usr/bin/env bash
set -e
# Akzeptiert CLI-Args: streamlit (default) oder python -m quant_trader.X
if [ "$1" = "streamlit" ] || [ -z "$1" ]; then
  exec streamlit run scripts/backtest_dashboard.py --server.address 0.0.0.0
else
  exec "$@"
fi
```

Damit kann man im Container ausfuehren:
- `docker compose exec qtrader` -> startet Streamlit
- `docker compose exec qtrader python -m quant_trader.backtest run ...`
  -> Backtest-CLI

### 5. `.github/workflows/ci.yml`

GitHub Actions Workflow auf `push` und `pull_request` zu `main`:
- `jobs.test`:
  - `actions/checkout@v4`
  - `actions/setup-python@v5` mit `python-version: "3.12"`
  - `pip install uv`
  - `uv sync --all-extras`
  - `uv run ruff check src tests`
  - `uv run ruff format --check src tests`
  - `uv run mypy src`
  - `uv run pytest -m "not live and not slow"`
- `jobs.docker` (needs test):
  - `docker/build-push-action@v5` mit `push: false, load: true`
  - Verifiziert dass das Image gebaut werden kann (kein Push zu Registry)

### 6. `pyproject.toml`-Anpassung

- `dockerignore` Sektion (oder in `tool.uv` oder als Standalone-File)
- KEINE Package-Config-Aenderung noetig

## Consequences

**Positiv**
- Reproduzierbares Deployment via `docker compose up`
- CI-Build verhindert Merge von broken code
- Image < 500 MB durch Multi-Stage + slim-base
- Volumes ermoeglichen Persistenz von Cache, Reports, Journal
- `env_file` haelt Secrets ausserhalb des Images
- `stdin_open + tty` fuer interaktive CLI-Use-Cases
- Backward-Compat: 434 bestehende Tests unveraendert gruen

**Negativ**
- Multi-Stage-Build erhoeht Build-Komplexitaet (akzeptabel)
- `python:3.12-slim` Image ist ~150 MB; mit Code < 500 MB
- IBKRBroker im Container braucht TWS-Netzwerkzugriff (out of scope)
- Kein Production-Hardening (kein Non-Root-User, kein Health-Check,
  kein Resource-Limit) - YAGNI fuer persoenlichen Use-Case

**Neutral**
- CI laeuft nur auf push/PR zu main (kein nightly, kein scheduled)
- Image-Push zu Docker Hub / GHCR ist out-of-scope (spaeter)
- `docker compose` v1 vs v2: v2 nutzen (`docker compose` mit Space)

## Alternatives Considered

- **Single-Stage Dockerfile**: abgelehnt, Image zu gross (~1 GB)
- **Production-Image mit nginx + gunicorn**: abgelehnt, Streamlit
  hat eigenen Server; YAGNI fuer persoenlichen Use-Case
- **Kubernetes/Helm statt docker-compose**: out-of-scope, Phase 8+
- **GitLab CI statt GitHub Actions**: abgelehnt, Repo ist auf GitHub
- **Docker Hub / GHCR Auto-Push**: out-of-scope, manuelle Builds
- **Production-Hardening (non-root user, health-checks)**: YAGNI,
  kommt mit Phase 8 wenn Cloud-Deployment
- **Multi-Arch-Builds (ARM64)**: abgelehnt, x86_64-only
- **Separate docker-compose fuer dev (mit Mock-Broker-Service)**:
  abgelehnt, Mock-Broker ist in-process; separater Service macht
  Architektur komplizierter ohne Mehrwert

## References

- `Dockerfile` (NEU)
- `.dockerignore` (NEU)
- `docker-compose.yml` (NEU)
- `scripts/entrypoint.sh` (NEU)
- `.github/workflows/ci.yml` (NEU)
- `docs/SECURITY.md` (existiert aus Slice 5.3)
- `pyproject.toml` (existiert)
- `Makefile` (existiert)
- `docs/userstories/p7-ops/deployment.md` (US-P7.1)
- `docs/prd/p7-ops/deployment.md` (Slice-PRD)
- `docs/uml/p7-ops/deployment.md` (Container-Architektur)
- NFR-Ops-1 (Docker-Deployment)
