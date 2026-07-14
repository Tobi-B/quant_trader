# Phase 7 - Docker-Deployment: User Stories

Phase:    P7 Docker-Deployment
Status:   US-P7.1 DRAFT (Slice 7.1, wartet auf User-Approval)
Persona:  Tobias (privater Einsteiger-Trader)
Quelle:   Interview am 2026-07-14

Konvention: jede Story folgt INVEST + MoSCoW + T-Shirt-Size + Gherkin.
Nutzer-zentriert: das "Was & Warum", nicht das "Wie".

Slicing (1 grosser Slice, genehmigt 2026-07-14):
- **Slice 7.1** Docker-Deployment (Dockerfile + Compose + CI/CD)

Globale Defaults (aus Interview, 2026-07-14):
- Python 3.12 als Basis-Image
- Multi-Stage-Build (Builder + Runtime) fuer kleines finales Image
- docker-compose mit App-Service (Streamlit-Dashboard) + optionalem
  Mock-Broker-Service fuer lokales Live-Trading-Testen ohne TWS
- GitHub Actions CI: lint + test + mypy + docker build (kein push zu
  Docker Hub, nur Verifikation)

---

## Slice 7.1 - Docker-Deployment + CI/CD

Erstellt die Deployment-Pipeline: ein produktionsreifes Docker-Image
mit Streamlit-Dashboard + CLI, plus eine docker-compose-Konfiguration
fuer lokales Testen, plus eine GitHub-Actions-CI die lint/test/mypy/
build automatisch ausfuehrt.

### US-P7.1 - QuantTrader laeuft in Docker mit CI-Build

- **Als** Trader
- **moechte ich**, dass `docker compose up` das gesamte Projekt
  (Streamlit-Dashboard + CLI + Backtest-Reports persistent) startet,
  und dass jeder Git-Push automatisch lint/test/mypy/docker-build
  durchlaeuft,
- **damit** ich das System reproduzierbar deployen kann und
  Regressionen fruehzeitig erkenne.

- **Priority:** Should
- **Estimate:** M
- **Acceptance Criteria (Gherkin):**
  - **Given** das Repo mit `Dockerfile`, `docker-compose.yml`,
    `.dockerignore` und `.github/workflows/ci.yml`
  - **When** ich `docker compose up --build` lokal ausfuehre
  - **Then** startet ein Container mit `streamlit run
    scripts/backtest_dashboard.py --server.address 0.0.0.0`
  - **And** das Dashboard ist unter `http://localhost:8501`
    erreichbar
  - **And** `reports/` und `data/` werden als Volumes gemountet
    (persistent auf dem Host)
  - **And** `.env`-File wird via `env_file: .env` in den Container
    gemountet (FMP_KEY, ALPHAVANTAGE_KEY etc.)
  - **And** `docker compose exec qtrader python -m quant_trader.backtest run ...`
    funktioniert (CLI im Container zugaenglich)
  - **And** ein Git-Push zu main triggert GitHub Actions CI, die
    `make test`, `make lint`, `mypy --strict` und `docker build`
    ausfuehrt; alle muessen gruen sein
  - **And** der `Dockerfile` ist Multi-Stage (Builder + Runtime),
    finales Image < 500 MB, basiert auf `python:3.12-slim`
  - **And** `.dockerignore` schliesst `.venv`, `__pycache__`,
    `.pytest_cache`, `.mypy_cache`, `data/`, `reports/`, `*.pyc`,
    `.git/` aus

- **Out of Scope:** Production-Deployment (Cloud-Run, Kubernetes,
  Helm), Secrets-Management (Vault, etc.), HTTPS/Reverse-Proxy
  (Traefik, nginx), automatische Image-Push zu Docker Hub / GHCR
  (kommt spaeter), DB-Backup-Strategie, Monitoring/Prometheus,
  Health-Checks, Resource-Limits (CPU/Memory), Multi-Arch-Builds
  (ARM64/AMD64), Phase 8+ (Cloud-Deployment).

---

## Mapped NFRs (siehe docs/requirements/nfrs.md)

| Story   | NFR-IDs                                            |
|---------|----------------------------------------------------|
| US-P7.1 | NFR-Ops-1 (Docker-Deployment)                      |

---

## Definition of Done (Story 7.1)

- [ ] `Dockerfile` (Multi-Stage: builder + runtime, python:3.12-slim)
- [ ] `.dockerignore` schliesst Caches, .venv, data, reports, .git aus
- [ ] `docker-compose.yml` mit App-Service (Streamlit + CLI), Volumes
      fuer reports/data/.env
- [ ] `scripts/entrypoint.sh` startet Streamlit + akzeptiert CLI-Args
- [ ] `.github/workflows/ci.yml` (GitHub Actions) mit lint, test, mypy,
      docker build
- [ ] Dockerfile-Build lokal getestet (docker compose up erfolgreich)
- [ ] CI-Workflow YAML-valid
- [ ] Backward-Compat: alle 434 bestehenden Tests unveraendert gruen
- [ ] `make test`, `make lint`, `mypy --strict` gruen
- [ ] Conventional Commit `feat(p7-ops): slice 7.1 docker deployment`
- [ ] `docs/STATE.md` aktualisiert, Tag `p7-ops/7.1` gesetzt
- [ ] UML-Diagramm (Container-Architektur) APPROVED
