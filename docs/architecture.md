# Architecture and operational boundaries

```text
Browser (Firebase sign-in + welcome/status page)
                     |
                     v ID token
                FastAPI API --> plain-Python AgentRuntime
                                  |       |         |
                                  v       v         v
                           LLMProvider  Tools   Telemetry
                          OpenAI API /             |
                             vLLM                  v
                                  PostgreSQL + pgvector
                                  app data / traces /
                                  evaluations / pricing
                     ^
                     |
GitHub Actions (CI + deterministic eval + manual migrations)
```

## Foundation included

- **Identity:** FastAPI validates RS256 OIDC/Firebase JWTs against the configured JWKS URI, issuer, expiration, and audience. The hosted prototype uses Firebase Authentication; Keycloak-compatible OIDC settings remain available for deployments that use Keycloak. The API exposes `sub`, an optional username, roles, and groups as a principal.
- **Database:** PostgreSQL is the only application database. SQLAlchemy async sessions, Alembic, pgvector (1536-dimensional initial embeddings), conversation/document models, traces/spans, LLM/tool calls, evaluation datasets/cases/runs/scores, and time-bounded model pricing live in one schema.
- **LLM:** Agent code uses `LLMProvider`. `OpenAICompatibleProvider` calls `/chat/completions` via HTTP and supports vLLM-compatible endpoints. Hosted inference may incur provider charges. Pricing is data, not code constants; unknown catalog entries have unknown cost. Aggregates preserve `null` when no costs are known and expose priced/unknown call counts. Recorded prices are estimates, not provider billing facts.
- **Telemetry:** Agent code depends on the `Telemetry` protocol. `PostgreSQLTelemetry` persists traces, spans, model/tool calls. Prompt bodies and tool payloads are not stored by default; metadata uses an allowlist and explicit capture settings gate safe tool payloads.
- **Evaluations:** Internal evaluators cover exact and structured matching, JSON Schema, reference fields, and metadata-based latency/token/error thresholds. LLM judges use the same provider contract. Runs/scores can be persisted and compared against a prior baseline.
- **Web UI:** GitHub Pages publishes the static sign-in and status UI from `frontend/`; `docs/` is reserved for documentation. The frontend keeps `index.html` at its root and groups styles and scripts under `assets/css/` and `assets/js/`. It calls the Render API cross-origin, and the API restricts CORS to the configured Pages origin. After authentication the UI shows API, database, and authentication status; the ID token remains in browser memory. The UI does not provide chat; agent runs use the authenticated API.

## Security and data handling

Set `DATABASE_URL`, `OIDC_ISSUER_URL`, `OIDC_AUDIENCE`, and `CORS_ALLOW_ORIGINS` through the Render environment. `OIDC_JWKS_URL` overrides the issuer's default signing-key endpoint. The Pages workflow reads `PAGES_API_BASE_URL` and `FIREBASE_WEB_API_KEY` from GitHub Actions repository secrets and generates `frontend/assets/js/app-config.js` for the deployment artifact only. Both values are delivered to browsers and are not private credentials. Keep private credentials such as database passwords and model API keys in host secret settings and `.env` local/untracked. Never put private credentials in frontend config, source, tests, logs, or workflow YAML.

The API checks ownership before returning an individual trace; `platform-admin` and `platform-observer` client/realm roles can inspect traces across users. Aggregate system metrics are visible to authenticated users in this initial version. Applications with stricter tenant boundaries should add tenant IDs and enforce them in every query before multi-tenant use.

Captured LLM errors and tool errors are exception class names, not raw exception strings. Provider response bodies are not included in API errors. Tool arguments/results are opt-in and are only persisted when explicitly identified as safe and corresponding capture flags are enabled. Avoid sending personal, regulated, or confidential data to model providers unless the selected provider and applicable policy permit it.

## Repeatability and operations

Run `python scripts/bootstrap.py check|ci|test|eval|migrate|seed`. The small script gives developers and CI a shared command entry point; it is optional and starts no services. GitHub Actions provisions its PostgreSQL service, installs dependencies, applies migrations, then invokes `bootstrap.py ci`. Unit tests and deterministic evaluations need no infrastructure. Migrations and seed require a configured PostgreSQL URL. Apply migrations as a separate release step; do not rely on application startup to mutate production schema.

CI runs formatting, linting, strict type checks, and tests with Python 3.13+. A separate evaluation workflow runs the deterministic quality gate. The Render Blueprint describes the API service; Neon and Firebase are configured independently. A manual GitHub Actions workflow applies production database migrations using its dedicated secret. Do not add Docker Compose, Kubernetes, Redis, or a telemetry SaaS until measured needs justify them.

## Growth path

Dataset import/UI, richer evaluation execution/threshold configuration, full analytics rollups, embedding pipeline/index tuning, and production-grade rate limiting are follow-on work. Interfaces permit OpenTelemetry/Langfuse/Phoenix exporters, new LLM providers, and other evaluators without coupling agent implementations to them. Add queueing, caching, partitioning, or specialized observability only after load/reliability measurements call for it.
