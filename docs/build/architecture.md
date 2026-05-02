# Architecture

> Source: `DECISIONS.md` — R5 (Subsystem Boundaries & Module Structure)

---

## Style: Modular Monolith

Single FastAPI process. Single Postgres. Single Redis. Two ARQ worker pools. Strict module boundaries enforced in code and CI.

Modules can become services later. Today's boundaries are tomorrow's seams.

---

## Module Table

Each module owns its tables. It exposes a Python-level interface via `__init__.py` with an explicit `__all__`. No cross-module DB joins — cross-module data is composed at the service layer. Each module ships a `README.md` documenting: ownership, public interface, emitted events, consumed events.

| Module | Owns |
|--------|------|
| `accounts` | Account, AccountGroup, DebtAccount, DebtBalance, ManualAccount, balance reconciliation |
| `transactions` | Transaction, SplitAllocation, dedup, transfer pairing, refund pairing, payment groups |
| `ingest` | SimpleFIN client, OFX/QFX parser, CSV import, statement upload, ingestion pipeline up to classification handoff |
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
| `security` | Encryption key management, secret storage abstraction, privacy mode state |
| `platform` | Money/Decimal handling, FX rate management, time abstractions, common types |

---

## Inter-Module Communication

**Synchronous interface calls** — used for read paths and same-transaction writes. One module calls another's public Python interface directly.

**Domain events** — used for cross-cutting reactive logic. Subscribers do not know about each other. In v1, processed in-process:
- Synchronous handlers within the same DB transaction where ordering matters.
- Async handlers via ARQ worker queue for heavier or decoupled work.

Subsystems communicate via **`Recommendation` objects**, never by writing directly into another module's tables. See [domain-recommendations.md](domain-recommendations.md).

---

## Boundary Enforcement

**`import-linter`** runs in CI. PRs that violate module-to-module import rules fail the build.

Rules: each module may import from `platform` and from its own submodules. Cross-module imports go through the defined public interface (`__all__`), not internal submodules.

---

## Extensibility

Plugin contract via **`pluggy`**. Defined extension points:

- Auth providers (first committed plugin contract — local auth and OIDC are reference implementations)
- Aggregator providers
- Budget methods
- Debt strategies
- Insight providers
- Export formats
- Statement parsers

The public REST API the frontend uses is the same API plugins use and scripts use. No internal/external API split.
