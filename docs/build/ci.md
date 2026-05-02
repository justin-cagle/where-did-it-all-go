# CI Pipeline

> Source: `DECISIONS.md` — R11 D3, D4, D5 (CI/CD)

---

## Runner Topology

| Job type | Runner |
|----------|--------|
| Fast jobs: lint, type check, unit tests, frontend build | GitHub Actions hosted runners |
| Slow jobs: testcontainers integration tests, Docker image build, deployment | Self-hosted runner on homelab |

---

## Pipeline: Every PR

### Backend

| Step | Command |
|------|---------|
| Lint | `ruff check` |
| Format check | `ruff format --check` |
| Type check | `pyright --strict` |
| Unit tests | `pytest` (no markers) |
| Integration tests | `pytest -m integration` (testcontainers Postgres + Redis) |
| Migration test | Apply forward → downgrade → re-upgrade against populated test DB |
| Module boundary check | `import-linter` |
| Coverage threshold | Per-module thresholds enforced (see [testing.md](testing.md)) |

### Frontend

| Step | Command |
|------|---------|
| Lint | `eslint` |
| Format check | `prettier --check` |
| Type check | `tsc --noEmit` (strict) |
| Unit tests | `vitest` |
| Build check | `vite build` |
| Bundle size | Regression alert on size increase beyond threshold |

### Cross-Cutting

| Step | Notes |
|------|-------|
| API drift check | Generate OpenAPI spec → regenerate orval client → diff. Fails if frontend client is out of sync. |
| Docker build | Runs when infrastructure files change |
| Dependency security scan | `pip-audit`, `npm audit`, `trivy` |

---

## Pre-Commit Hooks (`pre-commit` framework)

Runs on changed files before every commit:

| Hook | Tool |
|------|------|
| Python lint + format | `ruff check` + `ruff format` |
| Frontend format | `prettier` (changed files only) |
| No merge conflict markers | Built-in check |
| No large files | Configurable size limit |
| Secret detection | `detect-secrets` or `gitleaks` |

Type checking and full test runs stay in CI — too slow for pre-commit.

---

## Deployment Pipeline (Merge to Main)

Triggered on merge to main. Manual trigger available.

1. Build Docker images.
2. Tag: immutable version tag + `latest`.
3. Push to `ghcr.io`.
4. Update homelab via watchtower or manual `docker compose pull && up -d`.

Deployment is optional/manual — main branch is always deployable but deployment is not automatic.
