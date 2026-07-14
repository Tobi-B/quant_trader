# Security Policy

This document captures the project's credential and secrets policy. It is
mandatory for every contributor and is reviewed at every phase release.

## Credentials Policy

### API-Keys (Data Providers) - NFR-Sec-1

All data-provider keys (Financial Modelling Prep, AlphaVantage, StockData.org,
and any future provider) are loaded from the local `.env` file only:

- `.env` is gitignored. Never commit it.
- `.env.example` documents the available key names without real values.
- Provider modules read keys via `Settings.*_key` (pydantic-settings) or,
  for FMP, directly from `os.environ["FINANCIAL_MODELLING_PREP_KEY"]`.
- If a key is rotated, update `.env` locally and re-deploy.
- If a key is suspected to be leaked: see incident response below.

### Broker Credentials (IBKR) - NFR-Sec-2

IBKR credentials (username, password, 2FA) are **never** persisted by this
project:

- They are not stored in `.env`, `Settings`, the SQLite journal, or any other
  config file.
- `IBKRBroker.connect()` calls `ib.connect(host, port, clientId)` **without**
  any credentials argument.
- The login happens manually at the TWS prompt when TWS asks the user to
  approve the API connection (IBKR's standard security model).
- The Trader must keep TWS authenticated and approve the API prompt.

This is by design. There is no OAuth-token-based auth for IBKR; the only
mechanism is the TWS login.

### What to Do When Credentials Are Suspected to Be Compromised

- **Data-Provider API-Key**: rotate the key in the provider's web console,
  update the local `.env`, and restart any running QuantTrader processes.
  Review provider usage logs for unauthorised calls.
- **IBKR**: change the password via the IBKR account management website,
  revoke any active API sessions, and re-authorise TWS. Audit the IBKR
  activity log for unauthorised trades.

## Docker-Image

- Das Dockerfile nutzt `env_file: .env` (docker-compose), NICHT
  COPY einer .env-Datei.
- `.dockerignore` schliesst `.env`, `.env.local`, `.env.example` aus.
- Secrets bleiben auf dem Host, nicht im Image.

## Audit

This policy is reviewed at every phase release (see `docs/STATE.md`).
Last reviewed: 2026-07-14 (Slice 7.1, P7 Docker-Deployment).