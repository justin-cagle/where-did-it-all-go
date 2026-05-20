# Changelog

## v0.4.0 — Correctness Hardening

**Released:** May 2026

Focus: debt amortization correctness and test infrastructure.

### Bug fixes

- **Fixed intra-account APR ordering in debt amortization** — debt balances within a single account are now correctly ordered by APR when applying the avalanche method. Previously, sub-balances on the same account could be processed in incorrect order.
- **Fixed mid-month payoff cascade** — when a debt is paid off mid-month, freed minimum payments now correctly flow to the next debt in the plan. The snowball flow accumulator was not resetting correctly after payoff.
- **Fixed snowball freed_minimums accumulator** — the accumulator that tracks freed minimum payments from paid-off debts was not carrying forward correctly across multiple payoff events in the same plan run.

### Testing

- Added 33 new property-based and integration tests covering debt amortization edge cases
- Test suite now completes in under 3 minutes (session-scoped testcontainers, 3-way CI parallelism)

---

## v0.3.2 — Test Infrastructure

**Released:** May 2026

### Changes

- Migrated to session-scoped testcontainers — one Postgres instance per test session instead of one per test, significantly reducing test runtime
- 3-way CI test parallelism via pytest-xdist
- Fixed admin bootstrap flow: admin users with no household were incorrectly sent to the `/waiting` queue instead of `/admin`

---

## v0.3.1 — AIO Image + Bootstrap Fix

**Released:** May 2026

### New

- **All-in-one Docker image** (`ghcr.io/justin-cagle/wdiag-aio`) — single `docker run` command to a fully working instance. Bundles Postgres, Redis, Caddy, the app, and both worker pools under supervisord.
- **GitHub Release automation** — releases are created automatically on version tags via GitHub Actions, including AIO and production image builds.
- **Demo mode indicator** — AIO instances show a banner on the login page with the default credentials.

### Bug fixes

- Fixed admin bootstrap flow: users created via bootstrap env vars were being redirected to `/waiting` instead of `/admin` in some cases.

---

## v0.3.0 — Full Feature Set

**Released:** May 2026

### New features

All backend domain modules complete and tested:

- **Accounts** — all types, account groups, debt account annotation, balance history
- **Transactions** — full lifecycle, splits, transfer pairing, refund pairing, deduplication, payment groups
- **Classification** — rules engine with conditions/actions/priority, income sources, paycheck split-deposit detection
- **Budgets** — all six methods, rollover policies, versioning, income strategies
- **Debts** — avalanche/snowball/custom plans, amortization, comparison view
- **Goals** — all eight goal types, burn-up tracking, completion policies, per-member attribution
- **Recurrences** — detected and declared, exceptions (skip/amount/date shift), deviation alerts
- **Calendar** — unified timeline, pay period view, breach warnings
- **Projections** — day-by-day simulation, scenarios/what-if, breach events, caching
- **AI insights** — all five providers, five privacy levels, token/cost budgets, Q&A, anomaly detection
- **Ingest** — SimpleFIN (full sync management, rate limiting, account mapping), OFX/CSV file import
- **Invitations** — full email delivery, link-only fallback, 72-hour expiry, resend, revoke
- **Admin panel** — registration control, user management, SMTP, backup, emergency read-only mode
- **FX / multi-currency** — Frankfurter rate fetching, per-transaction FX snapshot, home currency aggregation

Full React + TypeScript frontend with all features wired up.

---

## v0.2.0 — Core Financial Data Layer

**Released:** April 2026

### New features

- Accounts and account groups
- Transactions with full classification pipeline
- SimpleFIN and OFX/CSV ingest
- Recurrence detection and management
- Recommendations and HITL queue (backend)
- Budget tracking and actuals

---

## v0.1.0 — Foundation

**Released:** March 2026

### New features

- Docker Compose deployment stack (Postgres, Redis, Caddy, ARQ workers)
- FastAPI backend with SQLAlchemy 2.0 async
- React + TypeScript frontend (Vite, TanStack Query, Zustand, shadcn/ui)
- Authentication: local auth (username + password + TOTP), session management
- Household model with visibility modes
- CI pipeline (ruff, pyright, pytest, vitest, import-linter, Playwright)
- Pre-commit hooks
- Alembic migrations baseline
