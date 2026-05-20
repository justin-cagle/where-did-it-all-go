# Quick Start (Demo)

The all-in-one (AIO) image is the fastest way to run WDIAG. It bundles Postgres, Redis, the app, background workers, and a reverse proxy into a single container.

## Ephemeral (data wiped on container removal)

```bash
docker run -p 80:80 -p 443:443 \
  ghcr.io/justin-cagle/wdiag-aio:latest
```

Open **https://localhost**. Accept the self-signed certificate warning (expected for localhost).

## With persistence (data survives container removal)

```bash
docker run -p 80:80 -p 443:443 \
  -v wdiag-data:/var/lib/postgresql/data \
  -e PERSIST_DATA=true \
  ghcr.io/justin-cagle/wdiag-aio:latest
```

The volume `wdiag-data` stores Postgres data. On subsequent starts with this volume, the data is preserved and the bootstrap credentials are not regenerated.

## Custom domain (LAN use)

To access over your local network at a hostname (e.g., `budget.home.lan`):

```bash
docker run -p 80:80 -p 443:443 \
  -v wdiag-data:/var/lib/postgresql/data \
  -e PERSIST_DATA=true \
  -e DOMAIN_NAME=budget.home.lan \
  ghcr.io/justin-cagle/wdiag-aio:latest
```

Note: Caddy will use a local CA for non-public hostnames. You may need to install the CA certificate in your browser to avoid the warning.

## What's inside the AIO image

The AIO image runs all services under `supervisord`:

| Process | What it does |
|---------|-------------|
| Postgres | Database (internal port 5432) |
| Redis | Job queue and cache (internal port 6379) |
| Caddy | Reverse proxy and TLS termination (ports 80, 443) |
| uvicorn | FastAPI application (internal port 8000) |
| arq-fast | Fast background worker pool |
| arq-slow | Slow background worker pool (nightly jobs, syncs) |

## Default credentials

```
Email:    admin@wdiag.local
Password: admin
```

Printed in container logs on first start. Shown on the login page. **Change them immediately** in Settings → Profile.

To change the password: log in → click your name → Settings → Profile → Change Password.

## AIO limitations

The AIO image is suitable for personal use and evaluation. It is not recommended for production multi-user deployments because:

- All services share one process space — no isolation between components
- No horizontal scaling
- The encryption key is auto-generated and stored in the container volume (if not provided via `-e MASTER_KEY=...`)

For a production deployment with multiple users or higher availability requirements, use the [docker-compose stack](production.md).
