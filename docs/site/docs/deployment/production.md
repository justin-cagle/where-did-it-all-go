# Production Setup

## Prerequisites

- Docker 24+ and Docker Compose v2
- A server with at least 1 GB RAM (2 GB recommended)
- A domain name with DNS A record pointing to your server
- Ports 80 and 443 reachable from the internet (for Let's Encrypt)

## Step 1 — Clone and configure

```bash
git clone https://github.com/justin-cagle/where-did-it-all-go.git
cd where-did-it-all-go
cp .env.example .env
```

## Step 2 — Generate required secrets

```bash
# Master encryption key (required)
openssl rand -hex 32

# Backup encryption key (recommended)
openssl rand -hex 32

# Strong Postgres password
openssl rand -base64 24
```

## Step 3 — Edit `.env`

Minimum required configuration:

```bash
# Postgres
POSTGRES_PASSWORD=<generated-above>

# App
MASTER_KEY=<generated-above>
DOMAIN_NAME=budget.yourdomain.com
CADDY_EMAIL=you@yourdomain.com

# Backup (recommended)
BACKUP_ENCRYPTION_KEY=<generated-above>
```

Set `COMPOSE_PROFILES=bundled-proxy` (already the default in `.env.example`) to use the bundled Caddy reverse proxy.

## Step 4 — Start the stack

```bash
docker compose up -d
```

First start pulls images, initializes Postgres, runs database migrations automatically, and starts all services. This takes 30–60 seconds.

## Step 5 — Create the first admin

Add to `.env` temporarily:

```bash
BOOTSTRAP_ADMIN_EMAIL=admin@yourdomain.com
BOOTSTRAP_ADMIN_PASSWORD=a-strong-password-here
```

Then restart the app:

```bash
docker compose up -d app
```

The admin account is created on startup. Remove the bootstrap variables from `.env` once the account is created (they're ignored on subsequent starts when users exist).

## Step 6 — Verify the stack is healthy

```bash
# All containers should show "running"
docker compose ps

# Health endpoint
curl https://budget.yourdomain.com/health

# Check admin panel
# Navigate to https://budget.yourdomain.com/admin
# System page shows worker pool status and migration state
```

## Step 7 — Point your domain

If you haven't already, create an A record in your DNS:

```
budget.yourdomain.com → your-server-ip
```

Caddy handles HTTPS automatically via Let's Encrypt once DNS propagates (usually within a few minutes, sometimes up to an hour).

## Stack services

| Service | Purpose |
|---------|---------|
| `migrate` | Runs `alembic upgrade head` on every start; exits when complete |
| `app` | FastAPI application (`wdiag-backend` image) |
| `worker-fast` | Fast background job pool — classification, notifications (`wdiag-backend` image) |
| `worker-slow` | Slow background job pool — syncs, backups, projection runs (`wdiag-backend` image) |
| `frontend` | nginx serving the compiled React SPA (`wdiag-frontend` image) |
| `postgres` | Primary database |
| `redis` | Job queue broker and cache |
| `caddy` | Reverse proxy, TLS termination (when `bundled-proxy` profile active) |

## Next steps

- [Configuration Reference](configuration.md) — all environment variables
- [Backup & Restore](backup-restore.md) — set up offsite backup
- [Connecting Your Bank](../getting-started/connecting-bank.md) — connect SimpleFIN
