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

   If Neon shows `postgresql://`, replace that scheme with `postgresql+asyncpg://`. `sslmode=require` is translated to `ssl=require` by the app for asyncpg compatibility. Neon URLs may include `channel_binding=require`, which is a libpq option and is not accepted by asyncpg; the app removes that option before connecting. Preserve other provider-supplied parameters and URL-encode special characters in credentials.
4. Keep the provider's **direct** connection string too. Use that direct URL for the one-time migration workflow; use the pooled URL for the running API.

The initial migration creates the `vector` extension and application tables. The database role must be allowed to create that extension.

### 2. Configure Firebase Authentication

1. Open the [Firebase Console](https://console.firebase.google.com/) and create a project. You can disable Google Analytics if you do not need it. In **Project settings → General**, copy the **Project ID** exactly; it is not the project display name.
2. In **Build → Authentication → Get started → Sign-in method**, enable **Email/Password** for the simplest prototype. Save the change.
3. For a quick test account, open **Authentication → Users → Add user**, enter an email and a strong password, and save. In a real app, provide a sign-up/sign-in screen using the Firebase client SDK instead of creating users manually.
4. If you have a browser-based client, register a web app in **Project settings → General → Your apps → Add app → Web**. Use the Firebase client SDK configuration in that frontend. The Firebase Web API key is intended to identify the Firebase project in client apps; it is not a substitute for authentication and does not authorize access to this API. In **Authentication → Settings → Authorized domains**, add the exact domain where the frontend runs if Firebase requires it. Do not add the API's Render domain unless the frontend itself is served from that domain.
5. In Render, open the API service and go to **Environment**. Add or verify the following variables, replacing the placeholder with the Project ID copied in step 1:

   ```text
   OIDC_ISSUER_URL=https://securetoken.google.com/<firebase-project-id>
   OIDC_AUDIENCE=<firebase-project-id>
   OIDC_JWKS_URL=https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com
   ```

   These are public project/token-validation settings, not secrets. Save the environment changes and let Render redeploy. Firebase ID tokens use the secure-token issuer and the Firebase Project ID as their audience; the API verifies their signature against Google's public signing keys.
6. Your frontend signs the user in with Firebase Authentication and sends the resulting **ID token** to the API:

   ```http
   Authorization: Bearer <firebase-id-token>
   ```

   The API does not provide a login or registration page. For a basic manual smoke test without a frontend, you can request a token from Firebase's Identity Toolkit REST API using the test user's email/password and the Firebase Web API key. Send the request body as JSON to:

   ```text
   https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=<firebase-web-api-key>
   ```

   Include `{"email":"<test-user-email>","password":"<test-user-password>","returnSecureToken":true}` as the JSON body. The response contains `idToken`; use that value as the bearer token when calling `GET https://<your-render-service>.onrender.com/v1/me`. Treat the ID token and test password as credentials: do not commit them, share them, or put them in a URL. Revoke/delete the test account when it is no longer needed.
7. Most `/v1` routes require a valid Firebase ID token. `POST /v1/admin/model-pricing` additionally requires a `platform-admin` role. This API currently extracts roles from Keycloak-shaped `realm_access.roles` and `resource_access.<client>.roles` claims; ordinary Firebase ID tokens do not include those claims by default. Treat the admin endpoint as unavailable with a basic Firebase setup unless the API is extended to read a trusted Firebase custom role claim. Never let a client set its own admin claim.

### 3. Run the one-time database migration from GitHub

This runs on a temporary GitHub Actions runner, not your computer or the deployed API:

1. Open this repository on GitHub (not your personal profile settings) and go to **Settings → Secrets and variables → Actions**.
2. Under **Repository secrets**, click **New repository secret**. Enter `MIGRATION_DATABASE_URL` as the **Name** and paste the **direct** Neon connection URL as the **Secret** value. Use the asyncpg URL format described above, do not wrap it in quotes, and save it. The migration workflow reads this exact secret name. Do not put this direct URL in a workflow file, commit, issue, or pull request.
3. Go to **Actions → Migrate production database → Run workflow**. Select the branch you intend to deploy and click **Run workflow**.
4. Open the new workflow run and confirm it succeeds before deploying the API. Run it again only when a later code change adds a database migration.

The migration workflow is manual and serialized to avoid repeated or overlapping migration runs. The existing CI and deterministic evaluation workflows do not use this production database secret.

If the migration log says `connect() got an unexpected keyword argument 'sslmode'` or `'channel_binding'`, confirm the selected branch includes the asyncpg URL compatibility fix in `src/agent_platform/db_url.py` and `migrations/env.py`, then rerun the workflow. The compatibility code maps `sslmode` to asyncpg's `ssl` option and removes the libpq-only `channel_binding` option; do not put either option into the database password.

### Where each secret belongs

| Value | Store it here | Why |
| --- | --- | --- |
| `MIGRATION_DATABASE_URL` (direct Neon URL) | GitHub repository → **Settings → Secrets and variables → Actions → Repository secrets → New repository secret** | Read only by the manually triggered migration workflow. |
| `DATABASE_URL` (pooled Neon URL) | Render Dashboard → your API service → **Environment → Add Environment Variable** | Read by the running API. Do not add it as a GitHub secret for this setup. |
| `LLM_API_KEY` (only if enabling a model) | Render Dashboard → your API service → **Environment → Add Environment Variable** | Read by the running API. Do not add it to GitHub unless a future workflow specifically needs it. |
| Firebase Project ID, `OIDC_ISSUER_URL`, `OIDC_AUDIENCE`, and `OIDC_JWKS_URL` | Render service environment / `render.yaml` | These identify the Firebase project and public signing-key endpoint; they are configuration, not credentials. |
| Firebase service-account private key | Nowhere for this deployment | The API validates Firebase ID tokens using Google's public JWKS endpoint; it does not need a service-account private key. Never commit one. |

In GitHub, create a secret from the **repository's** Settings page, not your account's settings. In Render, use the service's environment settings and mark actual credentials as secret if the dashboard offers that option. Never put secret values in `render.yaml`, source files, or workflow YAML. GitHub Actions secrets are not automatically passed to Render's running service.

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
- Store `MIGRATION_DATABASE_URL` as a repository secret at **GitHub repository → Settings → Secrets and variables → Actions → Repository secrets**. Store the pooled runtime `DATABASE_URL` in the Render service's environment settings. They are different connection endpoints for different tasks.

## GitHub workflows

- **Agent Platform CI** provisions a temporary PostgreSQL/pgvector service and runs migrations and project checks.
- **Agent evaluations** runs the deterministic evaluation gate.
- **Migrate production database** is a manual workflow that requires `MIGRATION_DATABASE_URL`.

No Render deploy token is needed by GitHub Actions for this setup: connect the repository in Render and use its repository integration. GitHub Actions secrets are not automatically exposed to the running API.

## Documentation and local development

GitHub Pages can serve the static files in [`docs/`](docs/), but it does not host the API or its services. See [`docs/architecture.md`](docs/architecture.md) for system boundaries. The API can also be run locally, but this guide focuses on the hosted deployment.
