# Configuration Reference

All configuration is via environment variables in your `.env` file. Variables changed in `.env` require `docker compose up -d` to take effect. Some settings (registration, SMTP) can also be changed at runtime via the admin panel.

## Container images

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `IMAGE_TAG` | No | `latest` | Tag for both `wdiag-backend` and `wdiag-frontend` images. Set to a specific version (e.g. `0.4.0`) to pin both images to an immutable release. |
| `GITHUB_REPOSITORY_OWNER` | No | `local` | GitHub username or org that owns the container registry images. Set automatically in CI; override if self-hosting from a fork. |

## Core

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MASTER_KEY` | Yes | — | 32-byte hex master encryption key for sensitive fields (SimpleFIN tokens, OIDC secrets, AI keys). Generate with `openssl rand -hex 32`. Never commit. |
| `LOG_LEVEL` | No | `INFO` | Log verbosity. One of: `DEBUG`, `INFO`, `WARNING`, `ERROR`. At `INFO` and above, output is structured JSON. At `DEBUG` (with `DEBUG=true`), output is human-readable colored console format. |
| `DEBUG` | No | `false` | Enables debug mode. Sets cookies to HTTP-only (not Secure) and switches log output to colored console format. For local development only. Never enable in production. |
| `ALLOWED_ORIGINS` | No | — | Comma-separated CORS origins. Only needed if running the frontend dev server separately from the backend. |
| `FRONTEND_PORT` | No | `3000` | Host port the frontend container binds to. Override if port 3000 is already in use. |

## Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_USER` | No | `wdiag` | Postgres username |
| `POSTGRES_PASSWORD` | Yes | — | Postgres password |
| `POSTGRES_DB` | No | `wdiag` | Postgres database name |
| `DATABASE_URL` | No | auto-constructed | Override the full database connection URL. Use when connecting to an external Postgres instance. Format: `postgresql+asyncpg://user:password@host/db` | <!-- pragma: allowlist secret -->

## Redis

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | No | `redis://redis:6379/0` | Override to connect to an external Redis instance. |

## Auth and sessions

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOOTSTRAP_ADMIN_EMAIL` | Conditional | — | Email for the first admin account. Read once on startup when the database is empty. |
| `BOOTSTRAP_ADMIN_PASSWORD` | Conditional | — | Password for the first admin account. Read once on startup when the database is empty. |

## Registration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALLOW_REGISTRATION` | No | `false` | Whether unauthenticated users can create accounts via `/register`. Invited users always bypass this. |
| `REGISTRATION_LIMIT` | No | unset (unlimited) | Maximum active user accounts. Only enforced when `ALLOW_REGISTRATION=true`. Invited users bypass this limit. |
| `UNASSIGNED_ACCOUNT_TTL_DAYS` | No | `7` | Days before an unassigned account (no household, no pending invite) is hard-deleted by the cleanup job. |

## SMTP (email delivery)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SMTP_HOST` | No | — | SMTP server hostname. Email is disabled if not set. |
| `SMTP_PORT` | No | `587` | SMTP server port. |
| `SMTP_USERNAME` | No | — | SMTP authentication username. |
| `SMTP_PASSWORD` | No | — | SMTP authentication password. |
| `SMTP_FROM_ADDRESS` | No | — | The "From" address on outgoing emails. Required if `SMTP_HOST` is set. |
| `SMTP_USE_TLS` | No | `true` | Enable STARTTLS. |
| `APP_BASE_URL` | No | — | Base URL used to construct invitation links. Example: `https://budget.yourdomain.com`. |

## Reverse proxy (Caddy)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DOMAIN_NAME` | Yes (with bundled proxy) | `localhost` | Your domain name. Caddy uses this for TLS and virtual hosting. |
| `CADDY_EMAIL` | No | — | Email for Let's Encrypt certificate notifications. |
| `COMPOSE_PROFILES` | No | `bundled-proxy` | Compose profiles to activate. `bundled-proxy` includes Caddy. `ollama` includes a local Ollama instance. |

## Backup

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BACKUP_ENCRYPTION_KEY` | No | — | Key for encrypting backup files. Recommended. Generate with `openssl rand -hex 32`. |
| `BACKUP_S3_ENDPOINT` | No | — | S3-compatible endpoint URL for offsite backup. |
| `BACKUP_S3_BUCKET` | No | — | S3 bucket name. |
| `BACKUP_S3_ACCESS_KEY` | No | — | S3 access key. |
| `BACKUP_S3_SECRET_KEY` | No | — | S3 secret key. |

## AI providers

AI providers are configured in the application (Settings or Admin), not via env vars. The AI subsystem connects to local Ollama, local llama.cpp, Anthropic, or OpenAI based on your in-app configuration.

## Observability

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | — | OpenTelemetry collector endpoint. Leave unset to disable tracing. Example: `http://otel-collector:4318`. |

## AIO-specific

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PERSIST_DATA` | No | `false` | Set to `true` when mounting a volume for Postgres data in AIO mode. Signals the entrypoint to skip `initdb` on returning starts. |
| `AIO_MODE` | No | `false` | Set automatically by the AIO entrypoint. Signals the app to show the demo mode banner on the login page. |
