# Agent Platform

Agent Platform is a Python API for running AI agents. It uses Keycloak for sign-in, PostgreSQL with pgvector for data, and an OpenAI-compatible endpoint for model calls. GitHub Actions runs the project's checks and evaluation gate.

## Run locally

You need Python 3.13 or newer, [uv](https://docs.astral.sh/uv/), PostgreSQL with pgvector, and (for authenticated API requests) a Keycloak realm configured for this API.

1. Clone the repository and enter its directory.
2. Install the project and development tools:

   ```sh
   uv sync --dev
   ```

3. Create a PostgreSQL database and set up the connection and identity settings:

   ```sh
   cp .env.example .env
   ```

   Edit `.env` and set `DATABASE_URL`, `OIDC_ISSUER_URL`, and `OIDC_AUDIENCE`. `DATABASE_URL` should use the `postgresql+asyncpg://` scheme. The first migration enables the PostgreSQL `vector` extension, so pgvector must be installed on the database server.
4. Apply the database schema:

   ```sh
   uv run python scripts/bootstrap.py migrate
   ```

5. Start the API:

   ```sh
   uv run uvicorn agent_platform.api.main:app --app-dir src --reload
   ```

The API is available at `http://127.0.0.1:8000`. Open `/docs` for interactive API documentation. `/health` checks that the API is running; `/ready` also checks its database connection.

To run the included deterministic seed data (optional):

```sh
uv run python scripts/bootstrap.py seed
```

## Configure external services

### PostgreSQL with pgvector

Install PostgreSQL and pgvector using the instructions for your operating system or hosting provider. Create a database and a database user, then set `DATABASE_URL` in `.env`, for example:

```text
DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/<database>
```

Run the migration command above after creating the database. The app does not install or start PostgreSQL for you.

### Keycloak

Create a realm and an OpenID Connect client for the API in your Keycloak instance. Configure tokens issued for this API to include its audience, and include any roles or groups your application uses. Set:

```text
OIDC_ISSUER_URL=https://<keycloak-host>/realms/<realm>
OIDC_AUDIENCE=<api-audience>
```

The API uses the realm's standard JWKS endpoint to validate access tokens. Set `OIDC_JWKS_URL` in `.env` only if your realm uses a different endpoint. Authenticated API requests must include a Keycloak access token as a bearer token.

### Model provider (optional)

Agent runs need an OpenAI-compatible model endpoint. Set its base URL, API key (if required), and model name in `.env`:

```text
LLM_BASE_URL=https://<provider-host>/v1
LLM_API_KEY=<provider-api-key>
LLM_DEFAULT_MODEL=<model-name>
```

The API uses these settings for `POST /v1/agents/run`. Hosted providers may charge for model usage; check the provider's pricing and usage limits.

## Run checks

Install the development dependencies with `uv sync --dev`, then run:

```sh
uv run python scripts/bootstrap.py ci
uv run python scripts/bootstrap.py eval
```

`ci` runs formatting checks, lint, type checking, and tests. The evaluation command runs the deterministic evaluation gate. Unit tests and deterministic evaluations do not require live Keycloak or a model provider. Database migrations and seed data do require a configured PostgreSQL database.

## GitHub Actions and Pages

Pushes to `main` and pull requests run the workflows in `.github/workflows`: CI starts a temporary PostgreSQL/pgvector service and runs migrations and checks, while the evaluation workflow runs the deterministic quality gate. You can also start either workflow manually from the repository's **Actions** tab.

GitHub Pages can publish the documentation as a static site; it cannot run this FastAPI application or provide PostgreSQL, Keycloak, or a model provider. To publish the documentation:

1. Open the repository's **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select the `main` branch and the `/docs` folder, then save.

The documentation landing page is `docs/index.md`. The API and its external services must be run or hosted separately.
