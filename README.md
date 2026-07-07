# Lens Backend

This is the FastAPI backend for the Lens application. It acts as the central data ingestion point for your CI/CD pipelines and serves the REST API for the Lens dashboard.

## Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.12+)
- **Database**: [MongoDB](https://www.mongodb.com/) via [Motor](https://motor.readthedocs.io/en/stable/) (Asynchronous driver)
- **Caching & Rate Limiting**: [Redis](https://redis.io/)
- **Authentication**:
  - `joserfc`: For cryptographic verification of incoming OIDC JSON Web Tokens (JWTs) during metric ingestion.
  - `authlib`: For OAuth2 session-based login to the dashboard.
  - `itsdangerous`: For secure, signed session cookies.

## Authentication Architecture

Lens is designed to be highly secure and platform-agnostic, supporting standard OpenID Connect (OIDC) and OAuth2 flows.

### 1. Metric Ingestion (OIDC)

When your CI/CD pipelines (e.g., GitHub Actions, GitLab CI) send metrics to the `/api/v1/events` endpoint, they authenticate using **short-lived OIDC JWTs**. 

The backend dynamically fetches the provider's JSON Web Key Set (JWKS) to cryptographically verify the signature of the token. It then validates the claims against an explicitly allowed list of owners (`OIDC_ALLOWED_OWNERS`).

### 2. Dashboard Access (OAuth2)

To view the dashboard, users authenticate via a standard OAuth2 flow (e.g., "Login with GitHub", "Login with GitLab").

Upon successful authentication, the backend verifies the user's identity against an explicit whitelist (`OAUTH_ALLOWED_USERS`) and issues a securely signed, HttpOnly cookie containing the user's session data.

## Configuration

The backend is configured via environment variables. In production, these are typically provided via a `.env` file or directly to the Docker container.

### Core Settings
- `ENVIRONMENT`: Set to `development` or `production`.
- `MONGODB_URL`: The connection string for your MongoDB instance (e.g., `mongodb://localhost:27017/lens`).
- `REDIS_URL`: The connection string for your Redis instance (e.g., `redis://localhost:6379/0`).
- `CORS_ORIGINS`: JSON list of allowed CORS origins for the frontend.

### OIDC Ingestion Settings
- `OIDC_ISSUER_URL`: The OIDC issuer URL (e.g., `https://token.actions.githubusercontent.com` or `https://gitlab.com`).
- `OIDC_AUDIENCE`: The expected audience claim (e.g., `lens-telemetry`).
- `OIDC_ALLOWED_OWNERS`: A JSON list of allowed repository owners/namespaces. For example: `["my-org", "my-username"]`.

### OAuth2 Dashboard Login Settings
- `SESSION_SECRET_KEY`: A strong, random string used to sign session cookies.
- `OAUTH_CLIENT_ID`: Your OAuth application's client ID.
- `OAUTH_CLIENT_SECRET`: Your OAuth application's client secret.
- `OAUTH_AUTHORIZE_URL`: The provider's authorization endpoint.
- `OAUTH_TOKEN_URL`: The provider's token endpoint.
- `OAUTH_USERINFO_URL`: The provider's user info endpoint.
- `OAUTH_ALLOWED_USERS`: A JSON list of allowed users (by username, email, or ID). For example: `["my-username", "admin@myorg.com"]`.

## Local Development

The backend uses `uv` for lightning-fast dependency management.

1. **Install dependencies**:
   ```bash
   uv sync --all-extras --dev
   ```

2. **Run tests**:
   ```bash
   uv run pytest
   ```

3. **Run linters and type-checkers**:
   ```bash
   uv run ruff check .
   uv run basedpyright
   ```

4. **Start the development server**:
   ```bash
   uv run uvicorn src.main:app --reload --port 8000
   ```

*(Note: For local development, ensure you have a running MongoDB and Redis instance, or set `DATABASE_TYPE=mock` to use an in-memory mock repository).*


