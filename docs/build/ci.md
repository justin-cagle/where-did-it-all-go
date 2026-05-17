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
| Type check | `tsc -b` (strict) |
| Unit tests | `vitest` |
| Build check | `vite build` |
| Bundle size | Regression alert on size increase beyond threshold |

### E2E (main branch + manual trigger only)

Runs after the build job succeeds. Uses a self-hosted runner that has Docker Compose available.

| Step | Notes |
|------|-------|
| Install Playwright browsers | `playwright install --with-deps chromium` |
| Start full stack | `docker compose up -d`, wait for health |
| Run E2E suite | `playwright test` (chromium, 2 workers) |
| Upload HTML report | Uploaded as artifact on failure |

Trigger: `github.ref == 'refs/heads/main' || github.event_name == 'workflow_dispatch'`. Not run on feature-branch PRs.

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
