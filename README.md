# Agent Platform

Agent Platform is a Python 3.13+ FastAPI backend deployed to Render, with a sign-in and status UI served as static files from GitHub Pages. It uses Neon for PostgreSQL with pgvector and Firebase Authentication for tokens. The UI does not run on Render, keeping the Render service focused on the API. Review provider pricing and usage limits before deployment.

## What runs where

| Component | Service | Notes |
| --- | --- | --- |
| API | Render web service | One Docker service. |
| Sign-in/status UI | GitHub Pages | Static HTML, CSS, and JavaScript; no frontend server. |
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
3. In **Authentication → Settings → Authorized domains**, add `ssnegi15.github.io` (hostname only; no scheme or repository path).
4. For a test account, open **Authentication → Users → Add user**, enter an email and a strong password, and save. Account creation is managed by the Firebase project administrator.
5. Register a web app in **Project settings → General → Your apps → Add app → Web** if the project does not already have one. Copy its **Web API Key** from the Firebase web-app configuration. This is public client configuration, not an admin credential.
   If you restrict this API key in Google Cloud Console, add the HTTP referrer `https://ssnegi15.github.io/*` and allow the Identity Toolkit API; otherwise browser sign-in may be rejected.
6. In Render, open the API service and go to **Environment**. Add or verify the following variables, replacing the placeholder with the Project ID copied in step 1:

   ```text
   OIDC_ISSUER_URL=https://securetoken.google.com/<firebase-project-id>
   OIDC_AUDIENCE=<firebase-project-id>
   OIDC_JWKS_URL=https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com
   ```

   The API verifies Firebase ID tokens using the issuer, audience, and Google's public signing keys.
7. In Render's environment, set `CORS_ALLOW_ORIGINS=https://ssnegi15.github.io`. This lets the GitHub Pages UI call the API from browsers; do not use `*`. Save changes and let Render redeploy.
8. Add frontend configuration as GitHub Actions repository secrets. Open this repository on GitHub and go to **Settings → Secrets and variables → Actions → Repository secrets → New repository secret**. Add:

   | Name | Value |
   | --- | --- |
   | `PAGES_API_BASE_URL` | The Render API origin, such as `https://<your-render-service>.onrender.com` (no trailing slash). |
   | `FIREBASE_WEB_API_KEY` | The Firebase Web API Key from step 5. |

   These settings are ultimately delivered to the browser, so they are not private credentials. The API URL and Firebase key are kept out of the repository; the Pages workflow creates `frontend/assets/js/app-config.js` only in the deployment artifact. Never put database URLs, model API keys, or Firebase service-account private keys in frontend settings.
9. Open **Repository → Settings → Pages**, set the source to **GitHub Actions**, and save. After deploying the API and adding both repository secrets, publish the UI using **Actions → Publish GitHub Pages UI → Run workflow**. The workflow also runs automatically when `frontend/` changes are pushed to `main`. Open `https://ssnegi15.github.io/Agentic-Platform/`, sign in, then use the separate **Test API**, **Test database**, and **Test sign-in** buttons. The **Available endpoints** explorer loads the API's OpenAPI operations and provides an individual call control for each endpoint, including editable JSON bodies and path/query parameters where applicable. This page has no chat functionality.

   For a manual protected-API smoke test, you can request a token from Firebase's Identity Toolkit REST API using the test user's email/password and the Firebase Web API key. Send the request body as JSON to:

   ```text
   https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=<firebase-web-api-key>
   ```

   Include `{"email":"<test-user-email>","password":"<test-user-password>","returnSecureToken":true}` as the JSON body. The response contains `idToken`; use that value as the bearer token when calling `GET https://<your-render-service>.onrender.com/v1/me`. Treat the ID token and test password as credentials: do not commit them, share them, or put them in a URL. Revoke/delete the test account when it is no longer needed.
**API authorization note:** Most `/v1` routes require a valid Firebase ID token. `POST /v1/admin/model-pricing` additionally requires a `platform-admin` role. This API currently extracts roles from Keycloak-shaped `realm_access.roles` and `resource_access.<client>.roles` claims; ordinary Firebase ID tokens do not include those claims by default. Treat the admin endpoint as unavailable with a basic Firebase setup unless the API is extended to read a trusted Firebase custom role claim. Never let a client set its own admin claim.

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
| Firebase Project ID, `OIDC_ISSUER_URL`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`, and `CORS_ALLOW_ORIGINS` | Render service environment / `render.yaml` | Backend token-validation and browser-origin configuration. |
| `PAGES_API_BASE_URL` and `FIREBASE_WEB_API_KEY` | GitHub repository → **Settings → Secrets and variables → Actions → Repository secrets** | Used by the Pages workflow to generate browser configuration at deployment time. These values are visible to site visitors after deployment and are not private credentials. |
| Firebase service-account private key | Nowhere for this deployment | The API validates Firebase ID tokens using Google's public JWKS endpoint; it does not need a service-account private key. Never commit one. |

In GitHub, create a secret from the **repository's** Settings page, not your account's settings. In Render, use the service's environment settings and mark actual credentials as secret if the dashboard offers that option. Never put secret values in `render.yaml`, source files, or workflow YAML. GitHub Actions secrets are not automatically passed to Render's running service.

### 4. Deploy the API to Render

1. Create a Render account and connect the GitHub repository.
2. Choose **New → Blueprint** and select this repository. Render reads [`render.yaml`](render.yaml), builds the small API container from [`Dockerfile`](Dockerfile), and configures one web service. The UI is not included in the Render container.
3. In the service's environment settings, set:

   ```text
   DATABASE_URL=<pooled Neon asyncpg URL>
   OIDC_ISSUER_URL=https://securetoken.google.com/<firebase-project-id>
   OIDC_AUDIENCE=<firebase-project-id>
   CORS_ALLOW_ORIGINS=https://ssnegi15.github.io
   ```

   The Firebase JWKS URL and privacy-conscious telemetry defaults are already in the Blueprint. CORS must allow only the GitHub Pages origin, not `*`. Do not put database passwords or model API keys in the repository or `render.yaml`.
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

   If Render stays at **Deploying**, open the service's **Events** page and the active deploy's **Logs** to distinguish an image-build failure from an application startup failure. A failed startup should show a Python traceback. The container should listen on Render's injected `PORT` and pass its `/health` check. Redeploy only after correcting the reported failure; avoid repeated deploy attempts while a build is already active.

### 5. Publish and browse the UI

Set the `PAGES_API_BASE_URL` and `FIREBASE_WEB_API_KEY` repository secrets described above. Set the Pages source to **GitHub Actions**, then run **Actions → Publish GitHub Pages UI → Run workflow**. Later changes under `frontend/` publish automatically when pushed to `main`. The GitHub Pages UI URL is:

- `https://ssnegi15.github.io/Agentic-Platform/` — sign in and view the welcome/status page.

The API endpoints remain on Render:

- `https://<your-render-service>.onrender.com/docs` — interactive Swagger API browser. Use **Authorize** and enter a Firebase ID token to try protected endpoints.
- `https://<your-render-service>.onrender.com/health` — checks that the API process responds.
- `https://<your-render-service>.onrender.com/ready` — checks that the API can also connect to Neon.

The UI calls Render directly from the browser. If sign-in works but service statuses show unavailable, confirm Render's `CORS_ALLOW_ORIGINS` exactly matches `https://ssnegi15.github.io`. Create users under Firebase **Authentication → Users**. The agent-run endpoint remains API-only and requires `LLM_BASE_URL` and `LLM_DEFAULT_MODEL`.

### 6. Optional model provider

The API and authenticated non-agent endpoints can run without an LLM provider. To enable `POST /v1/agents/run`, add these values in Render's environment settings:

```text
LLM_BASE_URL=https://<provider-host>/v1
LLM_API_KEY=<provider-key-if-required>
LLM_DEFAULT_MODEL=<model-name>
```

Choose a model that fits your budget and configure usage limits or billing alerts with the model provider where available. Hosting-provider limits do not cap model-provider charges.

## Keep usage within limits

- Keep one Render API service and one Neon project/branch; avoid preview environments and duplicate services.
- The API uses one worker and caps its SQLAlchemy connection pool at two connections with no overflow.
- Avoid uptime pingers, unnecessary load tests, and frequent manual redeploys to limit resource use.
- Keep `TELEMETRY_CAPTURE_INPUTS` and `TELEMETRY_CAPTURE_OUTPUTS` set to `false` unless you have a clear need to store user/model content.
- Leave model settings unset until needed. Track model-provider usage separately and set provider-side budgets where available.
- Use platform alerts and usage dashboards; provider quotas and pricing can change.
- Store `MIGRATION_DATABASE_URL` as a repository secret at **GitHub repository → Settings → Secrets and variables → Actions → Repository secrets**. Store the pooled runtime `DATABASE_URL` in the Render service's environment settings. They are different connection endpoints for different tasks.

## GitHub workflows

- **Agent Platform CI** provisions a temporary PostgreSQL/pgvector service and runs migrations and project checks.
- **Agent evaluations** runs the deterministic evaluation gate.
- **Migrate production database** is a manual workflow that requires `MIGRATION_DATABASE_URL`.

No Render deploy token is needed by GitHub Actions for this setup: connect the repository in Render and use its repository integration. GitHub Actions secrets are not automatically exposed to the running API.

## Documentation and local development

GitHub Pages publishes the static UI from [`frontend/`](frontend/); [`docs/`](docs/) contains project documentation only. The frontend keeps its entry page at the root and groups static assets by type:

```text
frontend/
├── index.html
└── assets/
    ├── css/
    │   └── app.css
    └── js/
        ├── app.js
        └── app-config.js  # generated by Actions; ignored by Git
```

Render hosts only the API; Neon and Firebase provide managed database and identity services. The Render API root returns service information; use `/docs` for its interactive API explorer. See [`docs/architecture.md`](docs/architecture.md) for system boundaries.
