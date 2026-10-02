# Agent Platform

Agent Platform is a Python 3.13+ FastAPI service. This guide deploys the API from GitHub to Render, uses Neon for PostgreSQL with pgvector, and uses Firebase Authentication for tokens. The goal is a small prototype footprint; free-tier quotas and terms can change, so check each provider's current dashboard and pricing before deployment. Free does not mean guaranteed always-on or zero cost.

## What runs where

| Component | Service | Notes |
| --- | --- | --- |
| API | Render web service | One Docker service on the free plan; it may sleep when idle. |
| PostgreSQL + pgvector | Neon | Use one project/branch and the pooled endpoint for the API. |
| User authentication | Firebase Authentication | Managed service; no Keycloak server to host. |
| Source and optional deployment migrations | GitHub | Existing Actions run CI/evaluations; a manual workflow applies database migrations. |
| Model endpoint | Optional OpenAI-compatible provider | Model usage may incur separate charges. Leave unconfigured until needed. |

Firebase Auth is managed by Google and is not an open-source replacement for Keycloak. It is the lower-operations choice here; this deployment no longer requires a Keycloak service or a second Keycloak database.

## Deploy step by step

### 1. Create the Neon database

1. Create a Neon account and one PostgreSQL project/branch.
2. In the project's connection details, copy the **pooled** connection string for the API. Keep the Neon project in one region near the Render service.
3. This application uses SQLAlchemy's `asyncpg` driver. Format the URL like this:

   ```text
   postgresql+asyncpg://<user>:<password>@<pooled-host>/<database>?ssl=require
   ```

   If Neon shows `postgresql://`, replace that scheme with `postgresql+asyncpg://`. If the URL query has `sslmode=require`, use `ssl=require` with this driver. Preserve any other provider-supplied connection parameters and URL-encode special characters in credentials.
4. Keep the provider's **direct** connection string too. Use that direct URL for the one-time migration workflow; use the pooled URL for the running API.

The initial migration creates the `vector` extension and application tables. The database role must be allowed to create that extension.

### 2. Configure Firebase Authentication

1. Create a Firebase project and note its **Project ID**.
2. In **Authentication → Sign-in method**, enable the sign-in provider your client will use (for a basic prototype, Email/Password).
3. Set the API token validation values using that exact Project ID:

   ```text
   OIDC_ISSUER_URL=https://securetoken.google.com/<firebase-project-id>
   OIDC_AUDIENCE=<firebase-project-id>
   OIDC_JWKS_URL=https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com
   ```

   Firebase ID tokens are signed JWTs. Send an ID token from Firebase as `Authorization: Bearer <id-token>` to authenticated API routes. Your client obtains that token through Firebase Authentication; the API does not implement a login page.
4. Most `/v1` endpoints accept an authenticated user token. `POST /v1/admin/model-pricing` additionally requires a `platform-admin` role. Firebase custom claims can carry that role; the API recognizes it under `realm_access.roles` or `resource_access.<client>.roles`. Do not grant admin claims to ordinary users.

### 3. Run the one-time database migration from GitHub

This runs on a temporary GitHub Actions runner, not your computer or the deployed API:

1. In GitHub, open **Settings → Secrets and variables → Actions** and create the repository secret `MIGRATION_DATABASE_URL`. Set it to the **direct** Neon URL, formatted for asyncpg as above.
2. Open **Actions → Migrate production database → Run workflow** and run it on the branch you intend to deploy.
3. Confirm the workflow succeeds before deploying the API. Run it again only when a later code change adds a database migration.

The migration workflow is manual and serialized to avoid repeated or overlapping migration runs. The existing CI and deterministic evaluation workflows do not use this production database secret.

### 4. Deploy the API to Render

1. Create a Render account and connect the GitHub repository.
2. Choose **New → Blueprint** and select this repository. Render reads [`render.yaml`](render.yaml), builds the small API container from [`Dockerfile`](Dockerfile), and configures a single free web service.
3. In the service's environment settings, set:

   ```text
   DATABASE_URL=<pooled Neon asyncpg URL>
   OIDC_ISSUER_URL=https://securetoken.google.com/<firebase-project-id>
   OIDC_AUDIENCE=<firebase-project-id>
   ```

   The Firebase JWKS URL and privacy-conscious telemetry defaults are already in the Blueprint. Do not put database passwords or API keys in the repository or `render.yaml`.
4. Deploy. When the service is live, test:

   ```text
   https://<your-render-service>.onrender.com/health
   https://<your-render-service>.onrender.com/ready
   ```

   `/health` verifies the process is responding; `/ready` also verifies database connectivity. Open `/docs` for the interactive API documentation.

   Once a client has signed in with Firebase and obtained an ID token, verify authentication with:

   ```sh
   curl https://<your-render-service>.onrender.com/v1/me \
     -H "Authorization: Bearer <firebase-id-token>"
   ```

### 5. Optional model provider

The API and authenticated non-agent endpoints can run without an LLM provider. To enable `POST /v1/agents/run`, add these values in Render's environment settings:

```text
LLM_BASE_URL=https://<provider-host>/v1
LLM_API_KEY=<provider-key-if-required>
LLM_DEFAULT_MODEL=<model-name>
```

Choose a low-cost model and configure usage limits or billing alerts with the model provider where available. Hosting free tiers do not cap model-provider charges.

## Keep usage within limits

- Keep one Render API service and one Neon project/branch; avoid preview environments and duplicate services.
- The API uses one worker and caps its SQLAlchemy connection pool at two connections with no overflow.
- Free web services may sleep when idle. Avoid uptime pingers, load tests, and frequent manual redeploys if conserving free usage matters.
- Keep `TELEMETRY_CAPTURE_INPUTS` and `TELEMETRY_CAPTURE_OUTPUTS` set to `false` unless you have a clear need to store user/model content.
- Leave model settings unset until needed. Track model-provider usage separately and set provider-side budgets where available.
- Use platform alerts/usage dashboards. Provider quotas and free-plan features change; monitor them rather than assuming that a particular limit is permanent.
- Store `MIGRATION_DATABASE_URL` in GitHub Actions secrets and runtime `DATABASE_URL` in Render's environment settings. They are different credentials/connection endpoints for different tasks.

## GitHub workflows

- **Agent Platform CI** provisions a temporary PostgreSQL/pgvector service and runs migrations and project checks.
- **Agent evaluations** runs the deterministic evaluation gate.
- **Migrate production database** is a manual workflow that requires `MIGRATION_DATABASE_URL`.

No Render deploy token is needed by GitHub Actions for this setup: connect the repository in Render and use its repository integration. GitHub Actions secrets are not automatically exposed to the running API.

## Documentation and local development

GitHub Pages can serve the static files in [`docs/`](docs/), but it does not host the API or its services. See [`docs/architecture.md`](docs/architecture.md) for system boundaries. The API can also be run locally, but this guide focuses on the hosted deployment.
