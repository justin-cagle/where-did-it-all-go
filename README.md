# WDIAG — Where Did It All Go

Personal finance budgeting and intelligence platform.

---

## Quick Start (Demo)

```bash
docker run -p 80:80 -p 443:443 \
  ghcr.io/justin-cagle/wdiag-aio:latest
```

Open https://localhost and accept the self-signed certificate warning.

Default credentials: `admin@wdiag.local` / `admin`

### With persistence

```bash
docker run -p 80:80 -p 443:443 \
  -v wdiag-data:/var/lib/postgresql/data \
  -e PERSIST_DATA=true \
  ghcr.io/justin-cagle/wdiag-aio:latest
```

### Production deployment

See [docs/build/deployment.md](docs/build/deployment.md) for the full docker-compose stack.

> The AIO image bundles Postgres, Redis, Caddy, and the application into a single
> container for demo and evaluation purposes. It is **not** recommended for
> multi-user production deployments.

---

## Docs

End-user documentation lives in `docs/site/`. Built with MkDocs Material.

**Local preview:**

```bash
pip install mkdocs-material
pnpm docs:serve
# or: cd docs/site && mkdocs serve
```

Then open http://127.0.0.1:8000.

**Build:**

```bash
pnpm docs:build
# or: cd docs/site && mkdocs build
```

Documentation is deployed to GitHub Pages automatically on push to `main` (see `.github/workflows/docs.yml`).
