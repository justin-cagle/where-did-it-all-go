# Deployment

> Source: `DECISIONS.md` — R9 (Deployment Topology)

---

## Default Compose Stack

The shipped `docker-compose.yml` includes everything:

| Service | Notes |
|---------|-------|
| Postgres 16+ | Primary DB |
| Redis | Worker queue broker + cache |
| `app` | FastAPI application |
| `worker-fast` | ARQ fast worker pool |
| `worker-slow` | ARQ slow worker pool |
| Caddy | Reverse proxy, TLS termination |
| Ollama | Optional — enabled via compose profile |

---

## BYO Mode

Users with existing infrastructure can disable any bundled service and point to their own via environment variables and compose profiles.

Examples:
- External Postgres: set `DATABASE_URL`, disable the `postgres` service.
- External Redis: set `REDIS_URL`, disable the `redis` service.
- External reverse proxy: disable the `bundled-proxy` compose profile.

---

## Reverse Proxy (Caddy)

Caddy is bundled by default. It listens on `:443`, handles auto-HTTPS via Let's Encrypt or a local CA, terminates TLS, and forwards plain HTTP to the app on the internal Docker network.

**No double-proxy.** Either Caddy is the TLS terminator, or the user's external proxy is. Never both.

When disabled (compose profile excludes `bundled-proxy`), the app exposes a plain HTTP port directly. The user's external proxy terminates TLS and routes to it.

Documentation includes per-proxy config snippets for: nginx, Traefik, Caddy external, with explicit notes on SSE requirements (e.g., `proxy_buffering off` for nginx — required for SSE to function).

---

## Secrets

**Bootstrap secrets via env vars** (master key + DB connection string). These are the only secrets that exist outside the app.

**Runtime secrets stored encrypted in DB:** SimpleFIN tokens, OIDC client secrets, AI provider API keys, OFX credentials. Decrypted only at use time. See [security.md](security.md).

---

## Observability

| Signal | Implementation |
|--------|---------------|
| Logs | `structlog` — structured JSON to stdout |
| Metrics | Prometheus `/metrics` endpoint — always on |
| Traces | OpenTelemetry — opt-in via `OTEL_EXPORTER_OTLP_ENDPOINT` env var |

Grafana is not bundled. Users bring their own or run a separate compose stack.

---

## Container Registry

**GitHub Container Registry (ghcr.io).**

Two tags per release:
- Immutable version tag: `ghcr.io/<user>/<app>:0.1.0`
- Moving tag: `ghcr.io/<user>/<app>:latest`

Private until first public release. Public after, under the chosen LICENSE. GitHub Actions uses `GITHUB_TOKEN` for registry auth — no separate credentials.
