# Build Context — Financial Budgeting App

> **Canonical source:** `DECISIONS.md` is the verified design ledger. If this document disagrees with the ledger, the ledger wins.

---

## Stack

**Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 async (typed `Mapped` style), Pydantic v2, Alembic, ARQ (Redis-backed worker queue), Postgres 16+, Redis.

**Frontend:** React (Vite SPA, no SSR), TypeScript strict (`noUncheckedIndexedAccess`, `noImplicitAny`), TanStack Query, Zustand, Tailwind CSS (`cva`, `clsx`), shadcn/ui, React Hook Form + Zod, Recharts, vite-plugin-pwa, Lucide icons.

**API client:** orval — generates typed TanStack Query hooks from FastAPI OpenAPI spec. Backend-frontend type sync enforced in CI.

**Quality:** pyright strict, ruff (lint + format), eslint, prettier, pytest, pytest-asyncio, hypothesis, testcontainers-python, polyfactory, time-machine, respx, pytest-cov, vitest, Playwright (E2E).

**Deployment:** Docker Compose (ships Postgres, Redis, app, worker-fast, worker-slow, Caddy, optional Ollama). BYO mode via env vars + compose profiles.

---

## Repository Layout

```
/
├── apps/
│   ├── backend/          # FastAPI app + worker
│   └── frontend/         # React SPA
├── packages/             # Shared specs (OpenAPI definitions, test fixtures)
├── docs/
│   └── design/           # DECISIONS.md, ADRs
├── docker-compose.yml
└── ...
```

Monorepo. `pnpm workspaces` for frontend. No Nx/Turborepo.

---

## Architecture

**Modular monolith.** Single FastAPI process, single Postgres, single Redis, two worker pools.

### Modules

Each module owns its tables, exposes a Python-level interface via `__init__.py` with explicit `__all__`. No cross-module DB joins. Cross-module data composed at service layer. Each module has a `README.md` documenting ownership, public interface, emitted events, consumed events.

| Module | Owns |
|--------|------|
| `accounts` | Account, AccountGroup, DebtAccount, DebtBalance, ManualAccount, balance reconciliation |
| `transactions` | Transaction, SplitAllocation, dedup, transfer pairing, refund pairing, payment groups |
| `ingest` | SimpleFIN client, OFX/QFX parser, CSV import, statement upload, ingestion pipeline |
| `classification` | Category (2-level hierarchy), Tag, rules engine, transaction-type detector, IncomeSource registry |
| `recurrences` | Declared/detected recurrences, RecurrenceCandidate, RecurrenceException, deviation alerts |
| `budgets` | Budget, BudgetLine, BudgetMethod implementations, period resolution, versioning |
| `debts` | DebtPlan, DebtBalance, payoff scheduling, strategy implementations (avalanche/snowball/custom/none) |
| `goals` | Goal entities (8 types), burn-up tracking, completion policies, funding sources |
| `projections` | Single projection engine; consumed by budgets, debts, goals, calendar |
| `recommendations` | Recommendation entity, HITL queue, routing, application |
| `insights` | InsightProvider abstraction, redaction layer, prompt templates, response handling, token/cost budget |
| `audit` | AuditEvent log (append-only), change capture, replay tooling |
| `households` | Household, User, membership, visibility modes, App Admin separation |
| `security` | Encryption key management, secret storage, privacy mode state |
| `platform` | Money/Decimal handling, FX rate management, time abstractions, common types |

### Inter-Module Communication

- **Synchronous interface calls** for read paths and same-transaction writes.
- **Domain events** for cross-cutting reactive logic. In-process for v1: synchronous handlers within DB transaction where appropriate; async handlers via ARQ for heavier work.

### Boundary Enforcement

`import-linter` in CI. PRs that violate module import rules fail.

---

## Data Layer Rules

### Database: Postgres 16+

- One schema (`public`), table prefixes per module (e.g., `accounts_account`, `audit_event`).
- **Money:** `NUMERIC(19, 4)` for all amounts. Every money column paired with `currency CHAR(3)`. In Python: `decimal.Decimal` everywhere. Pydantic validators reject floats at API boundaries. Never use float for money.
- **Identity:** UUIDv7 primary keys, app-side generated via `uuid_utils`.
- **System timestamps** (import time, audit, modification): `TIMESTAMPTZ`, stored UTC. Never `TIMESTAMP WITHOUT TIME ZONE`.
- **Bank-reported dates** (`posted_date`, `pending_date`, `occurred_at`): `DATE` columns, not `TIMESTAMPTZ`. No timezone conversion. If OFX provides datetime with TZ, extract date in source TZ. Validation: `posted_date` max 7 days in future.
- **Soft delete:** `archived_at TIMESTAMPTZ NULL`, `archived_by UUID NULL` on every user-facing entity. Default queries filter via SQLAlchemy `Live` mixin.
- **Versioning:** effective-dated rows (`effective_from`, `effective_to`; current = `effective_to IS NULL`). Used for: budgets, debt plans, APR history.
- **Migrations:** Alembic. Every schema change is a migration. No `Base.metadata.create_all()` in production. Reversible where possible. Each migration tested in CI (forward, downgrade, re-upgrade against populated DB).

### Audit Log

Append-only `audit_event` table. DB role has INSERT only (no UPDATE/DELETE).

Fields: `id` (UUIDv7), `occurred_at` (TIMESTAMPTZ), `actor_type` (user|system|automation), `actor_id` (UUID nullable), `actor_source` (text), `household_id` (FK), `entity_type` (text), `entity_id` (UUID), `operation` (create|update|delete|archive|merge|split|apply|accept|reject), `delta` (JSONB, RFC 6902 JSON Patch), `rationale` (text nullable), `source_event_id` (UUID nullable, links reversals).

Indexes: `(household_id, occurred_at DESC)`, `(entity_type, entity_id, occurred_at DESC)`.

Retention: forever.

---

## Domain Model Rules

### Households & Users

- Visibility mode selected at household creation, mutable: `fully_shared | separate_with_joint_view | role_based | admin_controlled`.
- Roles: `App Admin` (sysadmin, app-level settings) vs `Owner`/`Member` (household financial roles). Collapse to one human in single-user deploy.
- Auth pluggable via `pluggy`. Reference implementations: local auth (username+password+TOTP), OIDC. Auth is the first plugin contract.

### Accounts

- Manual/non-synced accounts first-class (cash, vehicles, real estate, crypto, etc.).
- `AccountGroup`: groups multiple feed entries representing one underlying account (e.g., one credit card appearing as two entries for primary + authorized user). `primary_holder` and `authorized_users[]` live on the group. Transactions from any feed entry roll up to the group. No double-counting. Detection heuristic: same institution + same balance + similar account name → candidate for grouping, surfaced to HITL.
- DebtAccount: annotation layer with `type ∈ {credit_card, loan, line_of_credit, ...}`. Parent of `DebtBalance` rows (multi-balance from day one). APR-with-history on every balance.

### Transactions

- Lifecycle state machine: `pending → posted → reconciled`.
- Splits are allocations, not children. Transaction stays atomic (single row, single amount). Split allocations tag/categorize portions. Sum of splits = transaction amount. Uncategorized remainder allowed. Budgets/reports aggregate over split allocations.
- Each split allocation has `attributed_to_user_id` (defaults to account primary holder) and `manually_categorized: bool`.
- `transaction_type` field populated by pre-rule classifier: `payroll | refund | transfer | fee | interest | dividend | regular`.
- Transfer pairing: internal (links to internal account) or external (links to nothing). Heuristic detection + manual override.
- Refund pairing: same merchant, opposite sign, within N days, debit ≥ credit.
- Payment groups: multi-source splits (purchase across cards, or split-funded transfer) linked as one logical event. Individual transactions retain per-account attribution.

### Deduplication

1. Prefer source-provided ID (SimpleFIN ID, OFX FITID).
2. Fuzzy match: account + amount + date ± N days + normalized description, with confidence score.
3. Below threshold → HITL queue.
4. Source merge: SimpleFIN wins canonical; statement is reference-only.

### FX

- Multi-currency from day one. Every money column has currency sibling.
- Household `home_currency` for rollups.
- Per-transaction FX snapshot (immutable historical truth) + daily rate table (current revaluation).
- Lazy currency population (only currencies with existing accounts/transactions).
- Daily rates only.
- For projections: foreign currencies project flat by default; configurable.

### Categories & Tags

- 2-level category hierarchy, household-scoped.
- Default tree seeded from editable template at household creation.
- System categories: `Transfer`, `Uncategorized`, `Income`, `Refund` — immutable DB rows (`system: true, deletable: false, renameable: false`), visible but locked.
- Tags: flat, many-to-many, household-scoped, orthogonal to categories.

### Classification Pipeline (strict order)

1. Transaction-type detection (pre-rule classifier)
2. IncomeSource match (locks to Income category regardless of merchant rules)
3. User rules (IF conditions THEN actions WITH priority)
4. Fallback → Uncategorized

### Rules Engine

- Shape: `IF (conditions) THEN (actions) WITH (priority)`. Explicit integer priority, user-editable. Ties broken by rule creation date (older wins).
- Conditions: `merchant_name`, `description`, `amount`, `account`, `direction`, `transaction_type`.
- Operators: `equals`, `contains`, `starts_with`, `regex` (UI: "advanced pattern match"), `amount_between`, `amount_equals`.
- Users can disable standard rules, define new ones.
- Suggest vs. auto-apply mode per rule.
- Manual recategorization sets `manually_categorized: true` — rule engine respects this.
- Rule provenance recorded on every auto-categorized allocation.
- Rules apply on ingest. Re-running on history is explicit user action.

### Strictness Setting (household-level, governs rules + recurrence + dedup + transfer detection)

- `strict` — multi-match → HITL, leave uncategorized. **DEFAULT.**
- `best_guess` — highest priority wins, flagged for review.
- `silent` — highest priority wins, no flag.

### IncomeSource

- Household-scoped, attributable to a user.
- Fields: `employer_name`, `attributed_to_user_id`, `expected_cadence`, `expected_amount_range`, `account_id`, `variability_model` (fixed | range | historical_distribution).
- Distinct sub-types: `income-payroll`, `income-bonus`, `income-rsu`, `income-reimbursement`.
- `deposit_split_pattern`: list of `{ account_id, amount_or_percentage }` for paycheck split deposits. Combined total = income for budget period.
- Income splits for lump-sum paychecks: same allocation mechanism as transaction splits.

### Recurrences

- Both detected and declared.
- Detected: ≥3 occurrences, consistent intervals, output as `RecurrenceCandidate`. Never auto-promote.
- Declared: user-defined, future-facing.
- User can flag single transaction as "start of new recurring series."
- Fields: `cadence`, `expected_amount` + tolerance, `expected_day_of_period`, `linked_category`, `linked_account`, `expected_amount_strategy` (fixed | last_n_average | manual_estimate | external_signal), `start_date`, optional `end_date`, `paused`.
- Missed/late detection: calendar shows "missed" indicator. Resets on reconciliation or manual dismissal. Dismissed alerts don't re-alert for same instance.
- Deviation alerts → HITL queue.
- Manual reconciliation override (detach transaction from recurrence without breaking series).
- Multi-source split detection → payment groups → HITL.
- `RecurrenceException` for single-instance overrides (skip, amount change, date shift).
- Editable and archivable, never deleted.
- Transactions carry `recurrence_id`.

### Budgets

- Plan vs. method separation. Budget is method-agnostic.
- Budget fields: name, period (monthly|weekly|biweekly|semimonthly|annual|custom), start/end dates, owning user or household, method.
- BudgetLines: one per category (or category+tag), with planned amount, currency, rollover policy.
- Multiple concurrent budgets per household.
- Scope: `{ accounts: [], categories: [], tags: [] }` — empty means "any."
- Rollover policies per line: `none | accumulate | accumulate_capped | debt_carry | reset_on_overspend`.
- Methods: `zero_based | envelope | 50_30_20 | percentage_based | rolling_average | manual | none`.
- `none` = pure tracking, no planned amounts, no constraints.
- Income strategy: `fixed | from_income_sources | last_period_actual | rolling_average | manual_per_period`.
- Versioned via effective-dated rows.
- Budgets can opt into pay-period boundaries instead of calendar-month.

### Debts

- DebtPlan: method (`avalanche | snowball | custom | none`), monthly extra payment budget, snowball-flow setting.
- `none` = tracked but no strategy active, no recommendations generated.
- Multi-balance debt accounts from day one. APR-with-history.
- Engine outputs: payoff schedule, total interest, time-to-debt-free, per-month payment recommendations.
- Plan-budget linkage via Recommendation objects (never direct writes).
- Versioned via effective-dated rows.

### Goals

- Types: `savings_target | purchase | debt_payoff | net_worth | category_reduction | emergency_fund | recurring_contribution | minimum_balance`.
- `minimum_balance`: no end date, alerts when balance drops below threshold, editable.
- Goals are 0+. No goal required.
- Funding strategy: `dedicated_account | virtual_allocation`.
- Funding sources: specific accounts, specific users' income streams, unified household stream. Per-user contribution attribution for jointly-funded goals.
- Contribution patterns (all three supported): manual, tag-driven, recurring rule.
- Conflict resolution: explicit per-period allocation.
- Burn-up tracking: `required_pace`, `actual_pace`, `cumulative_actual` vs `cumulative_expected`, `projected_completion_date`, `gap_to_close`, `status` (ahead|on_track|behind|at_risk|off_track).
- Uncapped accumulators. `progress_pct` can exceed 100.
- Completion policy per goal: `archive_on_complete | prompt_on_complete (DEFAULT) | auto_extend | auto_clone | convert_to_recurring`.

### Recommendations (cross-cutting entity)

- First-class entity. Subsystems communicate via recommendations, not direct writes.
- Fields: `target` (subsystem + entity), `proposed_value`, `rationale` (human-readable + structured), `source`, `confidence` (optional), `expires_at`.
- Routes through HITL queue by default. Per-source auto-apply switch available.
- Sources: debt engine, goal engine, recurrence detector, refund pairing, AI insights, classification pipeline.

### Projections Engine

- Single deterministic engine. Reused by debt scheduling, goal burn-ups, budget forecasts, calendar forward view, scenario analysis.
- Inputs: current balances, active recurrences, budgets, debt plans, goals, FX rates.
- Outputs: `ProjectedEvent` timeline per account (with confidence), aggregations (cash flow, balance curves, net worth curve), breach events.
- Hard cap: default 12 months, configurable up to 60.
- Scenario / what-if from day one: override deltas on base inputs. Saveable as named projections.
- Variable amount handling: `projection_strategy` per source (p25|p50|p75|last_n_average|manual_override). Default p50.
- Recompute: on-demand with caching (inputs hash + as_of date). Invalidated on input change.

### Calendar

- Layers: posted transactions, pending, expected recurrences (confidence-graded), budget period boundaries, goal milestones, debt due dates, HITL badges.
- Views: day, week, month, pay period.
- Pay period defined per IncomeSource. Multi-earner: user picks which drives the view, or selects "union of all" for visualization.
- Forward horizon matches projections engine.
- Click-through on future event: detail panel with source recurrence, confidence, edit/override options.
- Single-instance overrides → `RecurrenceException`.

### AI Insights

- Provider interface: `LocalOllama | LocalLlamaCpp | Anthropic | OpenAI | Disabled`.
- `provider_priority` per household. Graceful fallback.
- **AI is additive. App functions fully without any LLM. AI never on critical path.**
- LLM never touches DB directly. Receives structured data, returns structured output. Application layer applies.
- Insights become Recommendation objects → HITL queue.
- Audit trail on every LLM call: provider, model, prompt template, prompt fingerprint (hash), response, tokens, cost, household.
- Token/cost budget per household: `ai_token_budget`, `ai_cost_budget` (monthly caps). Overage: `block (DEFAULT) | warn_and_continue | silent`.
- Privacy levels (`ai_data_sharing`): `disabled | generalizations_only (DEFAULT for remote) | aggregates_only | redacted | full (local only, hard-gated)`.
- Redaction layer is security-critical code with per-level tests.

---

## API Rules

- **REST with OpenAPI.** FastAPI auto-generated spec. No GraphQL, no tRPC.
- **Public API parity.** Frontend uses what plugins use what scripts use. No internal/external split.
- URL: `/api/v1/households/{household_id}/...`. API paths with UUIDs appear only in network requests; frontend SPA routes use friendlier client-side paths.
- Auth: OIDC → JWT (15 min) + refresh token. Cookies: `httpOnly, Secure, SameSite=Strict`. Not localStorage.
- Idle timeout: configurable (default 30 min), App Admin settable.
- Real-time: SSE at `/api/v1/households/{household_id}/events`. Filtered by household membership.
- Offline: read-only. Service worker caches app shell + recent API GETs. No write queue.
- Pagination: cursor-based. Frontend presents as paginated or infinite scroll (user preference).
- Filtering: structured query params. Complex queries → dedicated endpoints.
- Errors: RFC 9457 (Problem Details).
- Idempotency keys: optional `Idempotency-Key` header on mutations.
- ETags / If-None-Match for cacheable reads.
- Bulk operations: explicit endpoints (e.g., `POST /transactions/bulk-categorize`).
- Programmatic access tokens: personal (per-user) and service (headless). Scoped, revocable, audited.

---

## Security Rules

- **Application-layer encryption** for: account numbers, routing numbers, aggregator credentials, OIDC tokens, AI provider API keys.
- Master key custody user-configurable: `env_var | file | vault`. App refuses to start if unsatisfiable. Re-key procedure for migration. Key rotation supported. Breach detection logging on failed decryption.
- Aggregator credentials: never logged, never sent to AI, encrypted at rest, rotatable.
- Step-up auth for App Admin actions (add member, change keys, export data): re-enter password or TOTP confirmation.
- Read-only panic switch (disables all writes including sync).
- Privacy viewing mode: per-device/session toggle. `full_blur` (••••) or `partial_blur` ($•,•••). Applied via `formatAmount()`. Does not apply to category names, merchant names, dates.
- Backup: nightly Postgres dump, encrypted, local + optional S3-compatible. Restore script tested in CI.
- **Use established libraries for security. Never roll custom auth/encryption/token handling.** Specifically: `passlib`/`argon2-cffi`, `python-jose`/`authlib`, `cryptography`, `authlib` for OIDC.
- Documented threat model: app-layer encryption protects against DB file theft, not full host compromise.

---

## Frontend Rules

- Business logic in `domain/` modules: pure TypeScript, no React, no DOM. **No business logic in components.** (Prep for React Native v2/v3.)
- TanStack Query hooks call into domain modules. React components are rendering + event wiring.
- SSE events trigger TanStack Query cache invalidations.
- Semantic CSS-variable tokens for all colors. No hardcoded colors. Theming: light + dark + system for v1.
- shadcn/ui as component foundation. Mantine `@mantine/dates` as exception for full calendar views.
- Lucide icons primary. Animated variants from lucide-animated.com where appropriate.
- Locale-specific number formatting per user via `Intl.NumberFormat` in `formatAmount()`.
- `formatAmount()` chains: locale format → privacy mode → output.
- First-class in-app charts (Recharts): net worth curve, cash flow, category breakdown, budget burn-down, goal burn-up, debt payoff schedule, calendar heatmap, recurrence consistency. All interactive, drill-downable.

---

## Background Jobs

- **ARQ** worker queue (Redis-backed, async-native).
- Two pools: `worker-fast` (short, high concurrency: event handlers, cache invalidation) and `worker-slow` (long, low concurrency: imports, AI calls, recurrence sweeps).
- All jobs: **idempotent**, **bounded** (hard timeouts), **observable** (structured logs), **decoupled from request handlers** (API enqueues, returns job ID).
- Scheduled: SimpleFIN polling, FX rate fetch (daily), recurrence detection, goal/budget recalc, backup (nightly).
- Triggered: recurrence updates, projection invalidation, AI insights, statement parsing, refund pairing.
- User-initiated: historical import, full re-categorization, scenario projections. Progress reporting via job status.

---

## Testing Rules

### Coverage Targets

| Module category | Target |
|----------------|--------|
| Financial logic (`projections`, `budgets`, `debts`, `goals`, `transactions`, `classification`, `recurrences`, `platform/money`, `platform/fx`) | 90%+ with Hypothesis property tests |
| Audit, security, recommendations | 85%+ with property tests on invariants |
| API routes, ingestion adapters, CLI | 70%+ |
| Workers, schedulers, plugin loaders | 60%+ |
| Frontend `domain/` modules | 90%+ (vitest) |
| Frontend components | Smoke + critical-path tests |

### Test Types

- Unit tests (pure logic, no I/O)
- Property tests (Hypothesis): financial invariants, dedup, recurrence, FX round-trip
- Integration tests (testcontainers Postgres + Redis)
- Golden-file tests: projection engine, debt amortization, budget period resolution
- Scenario tests: end-to-end through real DB + worker
- Migration tests: forward + downgrade + re-upgrade against populated data
- Contract tests: OpenAPI spec ↔ orval-generated frontend client (drift fails CI)
- E2E (Playwright): critical flows, nightly + release branches

---

## CI Pipeline (every PR)

**Backend:** ruff check, ruff format --check, pyright --strict, pytest (unit), pytest -m integration (testcontainers), Alembic migration test, import-linter, coverage threshold.

**Frontend:** eslint, prettier --check, tsc --noEmit, vitest, vite build, bundle size check.

**Cross-cutting:** OpenAPI → orval drift check, Docker build (infra changes), dep security scan (pip-audit, npm audit, trivy).

**Pre-commit:** ruff, prettier, no merge markers, no large files, secret detection (detect-secrets/gitleaks).

---

## Deployment

- Default compose ships: Postgres, Redis, app, worker-fast, worker-slow, Caddy, optional Ollama.
- BYO mode: compose profiles + env var overrides for external Postgres/Redis/proxy.
- Caddy: bundled by default, disable via profile. No double-proxy. SSE config documented for nginx/Traefik/Caddy.
- Bootstrap secrets via env (master key + DB connection). Runtime secrets encrypted in DB.
- Observability: structlog JSON to stdout, Prometheus `/metrics` always on, OpenTelemetry traces opt-in.
- Registry: ghcr.io. Tags: immutable version + `latest`. Private until first public release.

---

## Versioning

SemVer with strict criteria:
- **MAJOR:** breaking public API, plugin contract, schema requiring manual intervention, export format.
- **MINOR:** new feature, endpoint, plugin extension point, additive schema (auto-migrated).
- **PATCH:** bug fix, security fix, perf, internal refactor, docs.
- Pre-1.0: MINOR may include breaking changes (called out in changelog).
- Conventional Commits enforced. Auto-generated changelog.
- Release: tag → CI → Docker push → GitHub Release → docs site update.

---

## Extensibility

- Plugin contract via `pluggy`. Extension points: auth providers, aggregator providers, budget methods, debt strategies, insight providers, export formats, statement parsers.
- Webhook subsystem: outbound signed payloads, retry-with-backoff, dead-letter queue.
- Programmatic access tokens for API consumers.
- Per-module README for contributor orientation.

---

## NOT in v1 (explicitly deferred)

- Per-user category trees (household-scoped only)
- ML-assisted categorization (hooks left, no implementation)
- Multi-balance debt account UI polish (modeled in schema from day one, UI may ship simplified)
- Promotional balances (modeled, may not have full UI in v1)
- External-signal recurrence amount strategy (modeled in enum, data sources may not all be wired)
- Terminal-theme picker (architecture in v1, picker UI in v1.x)
- React Native build (v2/v3)
- Postgres read-replica for Grafana (documented, not implemented)
- Multi-tenant / federated deployment
- User-defined custom visualizations (v2+)
- Webhook subsystem (design committed, ship timing TBD)
- Goal priority ordering with auto-allocation (explicit per-period only)

---

## Cross-Cutting Principles

1. **Determinism is core; AI is decoration.** Every feature works without LLMs.
2. **Recommendations, not commands.** Subsystems suggest; user decides. HITL queue is the single inbox.
3. **Append, never mutate, history.** Audit log + soft delete + reversibility events.
4. **Strict classification pipeline order.** Type detection → income source → user rules → fallback.
5. **Public API is the only API.**
6. **Modular monolith with enforced boundaries.**
7. **Privacy-first AI defaults.** `generalizations_only` for remote; `full` for local only.
8. **Money is `Decimal`. Currency is always paired.**
9. **Bank dates are `DATE`; system timestamps are `TIMESTAMPTZ` (UTC).** Independent, never compared.
10. **Hardened means tested.** Property tests on financial logic; golden files on projections.
11. **Don't reinvent the wheel on security.** Use audited libraries. Never vibe-code security.
12. **Boring defaults, well-defended.**
