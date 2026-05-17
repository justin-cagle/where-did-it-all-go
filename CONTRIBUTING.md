# Contributing to WDIAG

## Project status

This project is in early, active development. The architecture is still being established — domain modules, data models, and core workflows are being built out incrementally per the design documents in `docs/`. Contributions that conflict with that roadmap will be declined regardless of quality. **Open an issue before you start work** so we can assess fit and avoid wasted effort on both sides.

Please read the [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

---

## How to contribute

1. **Open an issue first.** Describe what you want to do and why. This is where we agree on scope and approach before any code is written.
2. Fork the repository and create a branch from your fork's `main`.
3. Make your changes, write tests, and verify CI passes locally.
4. Open a pull request against this repo's `main` branch.

Pull requests opened directly against `main` without a corresponding issue will be closed without review. PRs that push to `main` without going through a fork-and-PR workflow are rejected.

---

## Development setup

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Python 3.12+
- Node.js 20+
- pnpm 10+ (`npm install -g pnpm`)

### Running locally

```bash
cp .env.example .env          # fill in required values
docker compose up             # starts Postgres, Redis, backend, and Caddy
```

The backend API is available at `http://localhost:8000` and the frontend dev server at `http://localhost:5173`.

Apply database migrations:

```bash
docker compose run --rm app alembic upgrade head
```

### Running tests

**Backend:**

```bash
cd apps/backend
uv sync --extra dev
uv run pytest -m "not integration"          # unit tests
uv run pytest -m integration               # integration tests (requires Docker)
```

**Frontend:**

```bash
cd apps/frontend
pnpm test                                  # vitest unit tests
pnpm typecheck                             # TypeScript strict check
pnpm lint                                  # ESLint
```

**E2E (Playwright):**

Requires the full stack running (backend + frontend dev server):

```bash
docker compose up -d                       # start backend
cd apps/frontend && pnpm dev &             # start frontend dev server
pnpm e2e                                   # run Playwright (headless)
pnpm e2e:headed                            # run with browser visible
pnpm e2e:report                            # open last HTML report
```

On first run, install Playwright's browser binaries:

```bash
npx playwright install --with-deps chromium
```

---

## Code standards

### Python

- Formatting and linting: `uv run ruff format . && uv run ruff check .`
- Type checking: `uv run pyright` (strict mode, zero errors)
- All monetary amounts must use `Decimal`, never `float`. The `MoneyDecimal` annotated type enforces this at the API boundary.
- Every schema change requires an Alembic migration. Migrations must be reversible.

### TypeScript

- Strict mode is non-negotiable — `noUncheckedIndexedAccess`, `noImplicitAny`, and all related flags are on.
- No business logic in components. Components render; domain logic lives in `src/domain/`.
- Formatting: `pnpm format` (Prettier)
- Linting: `pnpm lint` (ESLint)

### Tests

Coverage targets are enforced in CI. See [`docs/build/testing.md`](docs/build/testing.md) for the full breakdown by module category. The short version: financial logic requires 90%+ line coverage and Hypothesis property tests on every public function.

### Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add recurring transaction detection
fix: correct FX rate precision on EUR/CHF pair
chore: bump sqlalchemy to 2.0.50
docs: clarify soft-delete escape hatch
breaking: rename household_id to org_id across all tables
```

---

## Contributor License Agreement

By submitting a pull request, you agree that your contributions may be relicensed by the project maintainer under alternative license terms.
