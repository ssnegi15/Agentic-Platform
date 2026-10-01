# Agent Platform

An open-source, GitHub-first foundation for production-oriented AI agents. Agents are plain Python; authentication uses Keycloak OIDC; PostgreSQL with pgvector is the production data store. Provider, telemetry, tool, and evaluator contracts are internal interfaces so implementations can be replaced independently.

## Principles

- No Azure AI Foundry, Firebase Auth, local auth server, Ollama, mandatory SaaS, or required local containers.
- Hosted model calls can incur provider charges. Any costs recorded by this platform are estimates unless reconciled with provider billing.
- Secrets belong in environment configuration or deployment secret stores, never in Git.
- CI and evaluation checks run in GitHub Actions. Deployment authentication should use GitHub OIDC/workload identity when the hosting provider supports it.
- Local development and deployments use the same PostgreSQL and Keycloak/OIDC architecture; the app does not start infrastructure.

## Developer commands

Use Python 3.13+ and install the package with your preferred Python environment manager (for example `uv sync --dev`).

```sh
python scripts/bootstrap.py check
python scripts/bootstrap.py ci
python scripts/bootstrap.py format
python scripts/bootstrap.py lint
python scripts/bootstrap.py typecheck
python scripts/bootstrap.py test
python scripts/bootstrap.py eval
python scripts/bootstrap.py migrate
python scripts/bootstrap.py seed
uvicorn agent_platform.api.main:app --app-dir src
```

`bootstrap.py` is a small command entry point, not a service manager or required runtime component. It keeps local checks and CI on the same commands; `ci` runs formatting verification, linting, type checking, and tests. GitHub Actions installs Python/dependencies and provides the PostgreSQL service; bootstrap only invokes checks or migrations and never starts infrastructure. You can also run the underlying tools directly.

Set `DATABASE_URL`, `OIDC_ISSUER_URL`, and `OIDC_AUDIENCE` in the process environment for protected API and database operations. Copy `.env.example` to a local, ignored `.env` only if your chosen runner loads it. `check` reports absent deployment settings but does not require credentials for unit tests.

Alembic migrations install pgvector in PostgreSQL. Apply migrations before starting production traffic. Seed is safe to rerun and creates a minimal deterministic evaluation dataset; model prices are intentionally supplied by operators rather than guessed or embedded in code.

## Architecture

See [docs/architecture.md](docs/architecture.md) for platform boundaries, data handling, security assumptions, operations, and incremental growth.
