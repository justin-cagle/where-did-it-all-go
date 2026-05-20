# Installation

This guide sets up the full production docker-compose stack. Use this for any deployment you intend to keep.

## Prerequisites

- **Docker** 24+ and **Docker Compose** v2
- A server or VPS with at least 1 GB RAM
- A domain name pointing at your server (for TLS via Let's Encrypt)
- Ports 80 and 443 open

## Step 1 — Clone the repository

```bash
git clone https://github.com/justin-cagle/where-did-it-all-go.git
cd where-did-it-all-go
```

## Step 2 — Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` in a text editor and fill in the required values.

### Required variables

| Variable | Description | How to generate |
|----------|-------------|-----------------|
| `MASTER_KEY` | Master encryption key for sensitive fields | `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | Postgres database password | Choose a strong password |
| `DOMAIN_NAME` | Your domain name (e.g. `budget.example.com`) | Your DNS hostname |
| `CADDY_EMAIL` | Email for Let's Encrypt certificate notifications | Your email |

### Optional variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `wdiag` | Postgres username |
| `POSTGRES_DB` | `wdiag` | Postgres database name |
| `LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DEBUG` | `false` | Enable debug mode (HTTP cookies for local dev only) |
| `ALLOW_REGISTRATION` | `false` | Whether unauthenticated users can register |
| `REGISTRATION_LIMIT` | unset | Max active users (unlimited if unset) |
| `BACKUP_ENCRYPTION_KEY` | unset | Key for encrypting backup files (`openssl rand -hex 32`) |
| `BACKUP_S3_ENDPOINT` | unset | S3-compatible endpoint for offsite backups |
| `BACKUP_S3_BUCKET` | unset | S3 bucket name |
| `BACKUP_S3_ACCESS_KEY` | unset | S3 access key |
| `BACKUP_S3_SECRET_KEY` | unset | S3 secret key |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | OpenTelemetry collector URL (leave unset to disable tracing) |

## Step 3 — Start the stack

```bash
docker compose up -d
```

This starts: Postgres, Redis, the app, two background worker pools, and Caddy.

## Step 4 — Run migrations

```bash
docker compose exec app uv run alembic upgrade head
```

This applies all database migrations. It's safe to run repeatedly — Alembic only applies what hasn't been applied yet.

## Step 5 — Create the first admin account

Set the bootstrap variables and restart the app:

```bash
# Edit .env and add:
# BOOTSTRAP_ADMIN_EMAIL=admin@yourdomain.com
# BOOTSTRAP_ADMIN_PASSWORD=your-strong-password

docker compose up -d app
```

The app creates the admin account on startup when the database is empty, then ignores the bootstrap variables on all future starts.

Alternatively, use the CLI directly:

```bash
docker compose exec app uv run python -m app.admin create-admin \
  --email=admin@yourdomain.com \
  --password=your-strong-password
```

## Step 6 — Access the app

Navigate to `https://your-domain.com`. Caddy automatically obtains a Let's Encrypt certificate for your domain name (requires port 80 and 443 reachable from the internet).

## Step 7 — Verify health

```bash
docker compose ps          # all services should be "running"
curl https://your-domain.com/health  # should return {"status": "ok"}
```

Check the admin panel at `/admin` for system health: worker status, database size, and migration state.

## Next steps

- [First Setup](first-setup.md) — create your household and configure your instance
- [Connecting Your Bank](connecting-bank.md) — connect SimpleFIN
- [Configuration Reference](../deployment/configuration.md) — all environment variables
