# Testing

> Source: `DECISIONS.md` — R11 D6 (Testing Strategy)

---

## Coverage Targets

| Module category | Target | Notes |
|----------------|--------|-------|
| Financial logic: `projections`, `budgets`, `debts`, `goals`, `transactions`, `classification`, `recurrences`, `platform/money`, `platform/fx` | **90%+ line coverage** | Hypothesis property tests required on every public function |
| `audit`, `security`, `recommendations` | **85%+ line coverage** | Property tests on core invariants (audit append-only, encryption round-trip) |
| API routes, ingestion adapters, CLI tooling | **70%+ line coverage** | |
| Workers, schedulers, plugin loaders | **60%+ line coverage** | |
| Frontend `domain/` modules (pure TypeScript) | **90%+ coverage** | vitest |
| Frontend components | Smoke tests + critical-path component tests | No 100% chase |

Coverage thresholds are enforced per-module in CI. Falling below threshold fails the build.

---

## Test Types

### Unit Tests
Pure logic, no I/O. Fast. The bulk of the test suite.

### Property Tests (Hypothesis)
Required for all financial logic. Must cover:
- Financial invariants (sum of splits = transaction amount, budget rollover math, etc.)
- Deduplication logic (confidence scoring, merge rules)
- Recurrence pattern matching
- FX round-trip (convert → store → revalue → convert back)
- Encryption round-trip (encrypt → store → decrypt → verify)
- Audit log append-only invariant

### Integration Tests (testcontainers)
Real Postgres + Redis spun up per test run via testcontainers-python. Tests that exercise the actual DB, migrations, and ARQ workers.

### Golden-File Tests
For outputs that must be deterministically reproducible:
- Projection engine output (given input snapshot → expected ProjectedEvent timeline)
- Debt amortization schedule
- Budget period resolution

Golden files are committed to the repo. A change in output fails the test and forces deliberate update.

### Scenario Tests
End-to-end through real DB and real worker: ingest → classify → budget → recommend → accept. Verifies full flows, not just unit logic.

### Migration Tests
For every Alembic migration:
1. Apply forward against a populated test DB.
2. Downgrade.
3. Re-upgrade.
Run in CI on every PR that touches `alembic/versions/`.

### Contract Tests
OpenAPI spec (generated from FastAPI) → orval client regeneration → diff check. If the generated frontend client would change, the PR fails until the client is regenerated and committed. Backend and frontend are never silently out of sync.

### E2E Tests (Playwright)
A small set of critical user flows:
- Login → ingest → categorize → budget → recommendation accept
- Goal creation and contribution tracking
- Debt plan creation and payoff schedule view

Run nightly and on release branches. **Not run on every PR** (too slow).
