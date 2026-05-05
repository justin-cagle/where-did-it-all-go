# CLAUDE.md — Build Context

> Canonical design truth lives in `docs/design/DECISIONS.md` (human reference only — do not read).
> All build directives are in `docs/build/`. Read from there, not from `DECISIONS.md` or `CLAUDE_CONTEXT.md`.

---

## Do Not Read

These files exist for human design reference only. Do not load, reference, or summarize them:

- `DECISIONS.md` / `docs/design/DECISIONS.md`
- `CLAUDE_CONTEXT.md`

---

## Always Read Before Writing Any Code

```
docs/build/stack.md         — language, frameworks, libraries, tooling
docs/build/principles.md    — cross-cutting invariants and deferred items
docs/build/data-layer.md    — Postgres rules, money typing, timestamps, audit log
```

---

## Load On Demand (read when working in that area)

| You're touching… | Read this first |
|-----------------|-----------------|
| Households, users, auth, roles | `docs/build/domain-households.md` |
| Accounts, account groups, debt accounts | `docs/build/domain-accounts.md` |
| Transactions, splits, dedup, FX, transfers | `docs/build/domain-transactions.md` |
| Categories, tags, rules engine, income sources | `docs/build/domain-classification.md` |
| Recurrences, candidates, exceptions, deviation alerts | `docs/build/domain-recurrences.md` |
| Budgets, methods, rollover, versioning | `docs/build/domain-budgets.md` |
| Debt plans, payoff scheduling | `docs/build/domain-debts.md` |
| Goals, burn-up, completion policies | `docs/build/domain-goals.md` |
| Recommendations, HITL queue | `docs/build/domain-recommendations.md` |
| Projection engine, scenarios, caching | `docs/build/domain-projections.md` |
| Calendar layers, pay period, RecurrenceException | `docs/build/domain-calendar.md` |
| AI insights, providers, privacy levels, token budgets | `docs/build/domain-ai-insights.md` |
| API routes, pagination, SSE, auth flow, tokens | `docs/build/api.md` |
| Encryption, key custody, privacy mode, backup | `docs/build/security.md` |
| React components, state, charts, formatAmount, RN prep | `docs/build/frontend.md` |
| ARQ workers, job design, scheduled vs triggered jobs | `docs/build/background-jobs.md` |
| Test types, coverage targets | `docs/build/testing.md` |
| CI pipeline, pre-commit hooks | `docs/build/ci.md` |
| Docker Compose, secrets, observability, registry | `docs/build/deployment.md` |
| SemVer, plugin contract, webhook, release process | `docs/build/versioning.md` |

---

## Non-Negotiable Invariants (never violate these)

- **Money:** `decimal.Decimal` only. Never `float`. Every money column paired with `currency CHAR(3)`.
- **Timestamps:** bank-reported dates → `DATE`. System timestamps → `TIMESTAMPTZ` UTC. Never compare the two.
- **Identity:** UUIDv7 primary keys, app-side via `uuid_utils`.
- **Migrations:** Alembic only. No `Base.metadata.create_all()` in production paths.
- **Audit log:** append-only. DB role has INSERT only on `audit_event` — no UPDATE, no DELETE.
- **Soft delete:** `archived_at` / `archived_by` on every user-facing entity. Hard delete is admin-tool-only.
- **Module boundaries:** no cross-module DB joins. `import-linter` enforces this in CI.
- **Classification pipeline order:** type detection → IncomeSource match → user rules → fallback. Deterministic, no exceptions.
- **AI is never on the critical path.** Every feature works fully without any LLM.
- **Subsystems communicate via `Recommendation` objects.** No direct cross-module table writes.
- **Security:** use `passlib`/`argon2-cffi`, `authlib`, `cryptography`. Never roll custom auth or encryption.
- **API:** REST + OpenAPI only. No GraphQL. No tRPC. Public API parity — one API for frontend, plugins, and scripts.
- **Cookies:** `httpOnly`, `Secure`, `SameSite=Strict`. Never `localStorage` for tokens.
- **Frontend:** no business logic in React components. All logic in `domain/` (pure TS). `formatAmount()` for every monetary display.

---

## Stack (Quick Reference)

**Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 async (`Mapped` style), Pydantic v2, Alembic, ARQ, Postgres 16+, Redis.

**Frontend:** React + Vite SPA, TypeScript strict, TanStack Query, Zustand, Tailwind + cva + clsx, shadcn/ui, React Hook Form + Zod, Recharts, vite-plugin-pwa, Lucide icons, orval (OpenAPI-generated client).

**Quality:** pyright strict, ruff, eslint, prettier, pytest, hypothesis, testcontainers-python, vitest, Playwright.
