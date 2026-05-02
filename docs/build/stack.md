# Stack

> Source: `DECISIONS.md` — Language & Backend Stack, R10 (Frontend)

---

## Backend

| Layer | Choice |
|-------|--------|
| Language | Python 3.12+ |
| Web framework | FastAPI |
| ORM | SQLAlchemy 2.0 async, typed `Mapped` style |
| Validation | Pydantic v2 |
| Migrations | Alembic |
| Worker queue | ARQ (Redis-backed, async-native) |
| Database | Postgres 16+ |
| Cache / queue broker | Redis |

## Frontend

| Layer | Choice |
|-------|--------|
| Framework | React (Vite SPA — no SSR) |
| Language | TypeScript strict (`noUncheckedIndexedAccess`, `noImplicitAny`) |
| Server state | TanStack Query |
| Client state | Zustand |
| Styling | Tailwind CSS + `class-variance-authority (cva)` + `clsx` |
| Component library | shadcn/ui (owned source, copy-paste from CLI) |
| Forms | React Hook Form + Zod |
| Charts | Recharts |
| PWA | vite-plugin-pwa |
| Icons | Lucide (`lucide-react`); animated variants from lucide-animated.com |

## API Client

orval generates typed TypeScript clients **and** TanStack Query hooks from the FastAPI OpenAPI spec. Backend-frontend type sync is enforced in CI — drift fails the build.

## Quality Tooling

**Backend:** pyright strict, ruff (lint + format), pytest, pytest-asyncio, hypothesis, testcontainers-python, polyfactory, time-machine, respx, pytest-cov.

**Frontend:** eslint, prettier, vitest, Playwright (E2E).

## Deployment Runtime

Docker Compose. Default composition ships: Postgres, Redis, app, worker-fast, worker-slow, Caddy (reverse proxy), optional Ollama. BYO mode available via env vars and compose profiles.

## Monorepo

`pnpm workspaces` for the frontend. No Nx/Turborepo. Single git repo.

```
/
├── apps/
│   ├── backend/
│   └── frontend/
├── packages/         # Shared specs (OpenAPI definitions, test fixtures)
├── docs/
└── docker-compose.yml
```

## Discipline Rules (Backend)

- `decimal.Decimal` for all money. **Never float.**
- All schema changes via Alembic migrations. No `Base.metadata.create_all()` in production.
- SQLAlchemy 2.0 typed `Mapped` style.
- Async by default for all I/O.
- Workers run as separate processes, never in the request thread.
- Property-based tests (Hypothesis) for all financial logic.
- Golden-file tests for projection engine.
- Scenario tests (end-to-end through real DB and worker) for integration.
