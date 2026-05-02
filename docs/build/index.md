# Build Context — FinApp

> **Canonical source of truth:** `docs/design/DECISIONS.md`. If any file in this directory disagrees with the ledger, the ledger wins.

This directory contains the build-facing reference for Claude Code. Each file covers one topic. Read the relevant file(s) before writing code in that area.

---

## File Index

| File | Covers |
|------|--------|
| [stack.md](stack.md) | Language, frameworks, libraries, tooling |
| [architecture.md](architecture.md) | Modular monolith, module table, inter-module communication, boundary enforcement |
| [data-layer.md](data-layer.md) | Postgres rules, money/currency typing, identity, timestamps, soft delete, versioning, migrations, audit log |
| [domain-households.md](domain-households.md) | Household, User, visibility modes, roles, auth plugin contract |
| [domain-accounts.md](domain-accounts.md) | Account, AccountGroup, DebtAccount, DebtBalance, ManualAccount |
| [domain-transactions.md](domain-transactions.md) | Transaction lifecycle, splits/allocations, transfer/refund pairing, payment groups, deduplication, FX |
| [domain-classification.md](domain-classification.md) | Categories, tags, classification pipeline, rules engine, strictness setting, IncomeSource |
| [domain-recurrences.md](domain-recurrences.md) | Detected/declared recurrences, RecurrenceCandidate, RecurrenceException, missed detection, deviation alerts |
| [domain-budgets.md](domain-budgets.md) | Budget structure, BudgetLines, rollover policies, methods, income strategies, versioning |
| [domain-debts.md](domain-debts.md) | DebtPlan, strategies, engine outputs, plan-budget linkage, versioning |
| [domain-goals.md](domain-goals.md) | Goal types, funding strategy, contribution patterns, burn-up tracking, completion policies |
| [domain-recommendations.md](domain-recommendations.md) | Recommendation entity, HITL queue, routing, sources |
| [domain-projections.md](domain-projections.md) | Projection engine, inputs/outputs, scenarios, variable amount handling, caching |
| [domain-calendar.md](domain-calendar.md) | Calendar layers, views, pay period, click-through, RecurrenceException |
| [domain-ai-insights.md](domain-ai-insights.md) | Provider abstraction, insight categories, privacy levels, token/cost budgets, redaction layer |
| [api.md](api.md) | REST conventions, URL structure, auth, SSE, offline behavior, pagination, errors, tokens |
| [security.md](security.md) | Encryption at rest, key custody, key rotation, step-up auth, privacy mode, backup, libraries |
| [frontend.md](frontend.md) | Domain modules, state management, theming, component library, charts, formatAmount, RN prep |
| [background-jobs.md](background-jobs.md) | ARQ, worker pools, job categories, job design rules |
| [testing.md](testing.md) | Coverage targets, test types |
| [ci.md](ci.md) | CI pipeline per PR, pre-commit hooks |
| [deployment.md](deployment.md) | Docker Compose topology, BYO mode, secrets, observability, registry |
| [versioning.md](versioning.md) | SemVer criteria, Conventional Commits, release process, extensibility/plugin contract |
| [principles.md](principles.md) | Cross-cutting principles, deferred items (NOT in v1) |

---

## Repository Layout (reference)

```
/
├── apps/
│   ├── backend/          # FastAPI app + workers
│   └── frontend/         # React SPA
├── packages/             # Shared specs (OpenAPI definitions, test fixtures)
├── docs/
│   ├── design/           # DECISIONS.md, ADRs  ← source of truth
│   └── build/            # This directory — build-facing reference
├── docker-compose.yml
└── ...
```
