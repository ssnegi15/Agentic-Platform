# Architecture and operational boundaries

```text
GitHub Actions (CI + deterministic eval gate)
                     |
                     v
Keycloak --OIDC/JWT--> FastAPI --> plain-Python AgentRuntime
                                      |       |         |
                                      v       v         v
                               LLMProvider  Tools   Telemetry
                              OpenAI API /             |
                                 vLLM                  v
                                      PostgreSQL + pgvector
                                      app data / traces /
                                      evaluations / pricing
```

## Foundation included

- **Identity:** Keycloak issues access tokens; FastAPI validates RS256 JWTs against the realm JWKS URI, issuer, expiration, and configured audience. `sub`, `preferred_username`, realm/client roles, and the configured groups claim are exposed as a principal. Configure the API audience mapper and role/group claims in Keycloak. There is no local login fallback.
- **Database:** PostgreSQL is the only application database. SQLAlchemy async sessions, Alembic, pgvector (1536-dimensional initial embeddings), conversation/document models, traces/spans, LLM/tool calls, evaluation datasets/cases/runs/scores, and time-bounded model pricing live in one schema.
- **LLM:** Agent code uses `LLMProvider`. `OpenAICompatibleProvider` calls `/chat/completions` via HTTP and supports vLLM-compatible endpoints. Hosted inference is not free by default. Pricing is data, not code constants; unknown catalog entries have unknown cost. Aggregates preserve `null` when no costs are known and expose priced/unknown call counts. Recorded prices are estimates, not provider billing facts.
- **Telemetry:** Agent code depends on the `Telemetry` protocol. `PostgreSQLTelemetry` persists traces, spans, model/tool calls. Prompt bodies and tool payloads are not stored by default; metadata uses an allowlist and explicit capture settings gate safe tool payloads.
- **Evaluations:** Internal evaluators cover exact and structured matching, JSON Schema, reference fields, and metadata-based latency/token/error thresholds. LLM judges use the same provider contract. Runs/scores can be persisted and compared against a prior baseline.
- **Dashboard API:** Authenticated metrics and trace endpoints provide an initial backend for a first-party UI; a frontend is intentionally not bundled in this foundation.

## Security and data handling

Set `DATABASE_URL`, `OIDC_ISSUER_URL`, and `OIDC_AUDIENCE` through runtime environment or a deployment secret manager. `OIDC_JWKS_URL` can override Keycloak's standard realm certificate endpoint. Keep `.env` local and untracked; never place real credentials in source, tests, fixtures, logs, or CI YAML. Prefer short-lived GitHub OIDC/workload identity for cloud deployment instead of long-lived cloud keys.

The API checks ownership before returning an individual trace; `platform-admin` and `platform-observer` client/realm roles can inspect traces across users. Aggregate system metrics are visible to authenticated users in this initial version. Applications with stricter tenant boundaries should add tenant IDs and enforce them in every query before multi-tenant use.

Captured LLM errors and tool errors are exception class names, not raw exception strings. Provider response bodies are not included in API errors. Tool arguments/results are opt-in and are only persisted when explicitly identified as safe and corresponding capture flags are enabled. Avoid sending personal, regulated, or confidential data to model providers unless the selected provider and applicable policy permit it.

## Repeatability and operations

Run `python scripts/bootstrap.py check|ci|test|eval|migrate|seed`. The small script gives developers and CI a shared command entry point; it is optional and starts no services. GitHub Actions provisions its PostgreSQL service, installs dependencies, applies migrations, then invokes `bootstrap.py ci`. Unit tests and deterministic evaluations need no infrastructure. Migrations and seed require a configured PostgreSQL URL. Apply migrations as a separate release step; do not rely on application startup to mutate production schema.

CI runs formatting, linting, strict type checks, and tests with Python 3.13+. A separate required evaluation workflow runs the deterministic quality gate. Enable both status checks in GitHub branch protection/rulesets. No provider-neutral deploy action can safely provision an unspecified hosting target; connect deployment after choosing a runtime and PostgreSQL/Keycloak hosting, grant the GitHub environment only the required OIDC trust, and gate that job on both successful workflows. Do not add Docker Compose, Kubernetes, Redis, or a telemetry SaaS until measured needs justify them.

## Growth path

The first-party dashboard frontend, dataset import/UI, richer evaluation execution/threshold configuration, full analytics rollups, embedding pipeline/index tuning, and cloud-specific deployment workflow are follow-on work. Interfaces permit OpenTelemetry/Langfuse/Phoenix exporters, new LLM providers, and other evaluators without coupling agent implementations to them. Add queueing, caching, partitioning, or specialized observability only after load/reliability measurements call for it.
