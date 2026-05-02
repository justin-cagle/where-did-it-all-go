# Data Layer

> Source: `DECISIONS.md` — R6 (Data Layer), R4D (Audit)

---

## Database

**Postgres 16+.** Hard requirement.

One schema (`public`). Table names are prefixed per module: e.g., `accounts_account`, `transactions_transaction`, `audit_event`.

---

## Money & Currency

- **Column type:** `NUMERIC(19, 4)` for every monetary amount.
- **Currency pairing:** every money column has a sibling `currency CHAR(3)` column. No exceptions.
- **Python type:** `decimal.Decimal` everywhere. Never `float` for money.
- **API boundary:** Pydantic validators reject floats at API ingress. This is enforced, not advisory.
- **Display formatting:** locale-specific decimal/thousands formatting is a per-user preference. Implemented via `Intl.NumberFormat` in the frontend's `formatAmount()` function. The data layer stores raw `NUMERIC`; formatting is purely display-layer. Options: `1,234.56` (US/UK), `1.234,56` (EU/Latin America), `1 234,56` (French/Scandinavian), `1'234.56` (Swiss).

---

## Identity

**UUIDv7 primary keys**, generated app-side via the `uuid_utils` library. Time-ordered for index locality; not enumerable.

---

## Timestamps

Two distinct timestamp semantics — they are independent and never compared to each other:

| Kind | Column type | Stored as | Used for |
|------|-------------|-----------|---------|
| System-generated | `TIMESTAMPTZ` | UTC | Import time, audit events, `created_at`, `updated_at` |
| Bank-reported dates | `DATE` | Calendar date as reported | `posted_date`, `pending_date`, `occurred_at` |

**Never use `TIMESTAMP WITHOUT TIME ZONE`.** System timestamps are always `TIMESTAMPTZ` UTC.

**Bank-reported `DATE` columns:** no timezone conversion is applied. If an OFX source provides a full datetime with timezone, extract the date component in the source's timezone and store as `DATE` — do not UTC-convert, which could date-shift.

**Validation:** `posted_date` cannot be more than 7 days in the future. No validation comparing bank-reported dates to system import timestamps.

---

## Soft Delete

Every user-facing entity has:

```sql
archived_at  TIMESTAMPTZ NULL
archived_by  UUID        NULL
```

Default queries filter archived rows via a SQLAlchemy `Live` mixin or event hook. Hard delete is admin-tool-only and rare (e.g., GDPR removal).

---

## Versioning (Effective-Dated Rows)

Entities that need version history (budgets, debt plans, APR history on debt balances) use a single table with:

```sql
effective_from  DATE NOT NULL
effective_to    DATE NULL   -- NULL = current version
```

Current version query: `WHERE effective_to IS NULL`. Edits create a new row with a new `effective_from`; the previous row gets `effective_to` set. History is never rewritten.

---

## Migrations

**Alembic.** Every schema change is a migration script. `Base.metadata.create_all()` is never used in production paths.

Migrations are reversible where possible; documented when not. Each migration is tested in CI:

1. Apply forward against a populated test DB.
2. Downgrade.
3. Re-upgrade.

Auto-generated migrations are reviewed before commit — never blindly committed.

---

## Audit Log

Append-only `audit_event` table. The app's DB role has **INSERT only** — no UPDATE, no DELETE on this table. Enforced via DB role permissions, not application logic.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUIDv7 | |
| `occurred_at` | TIMESTAMPTZ | UTC |
| `actor_type` | text | `user \| system \| automation` |
| `actor_id` | UUID nullable | `user_id` when actor_type = user |
| `actor_source` | text | e.g., `'rule_engine'`, `'recurrence_detector'` |
| `household_id` | UUID FK | |
| `entity_type` | text | |
| `entity_id` | UUID | |
| `operation` | text | `create \| update \| delete \| archive \| merge \| split \| apply \| accept \| reject` |
| `delta` | JSONB | RFC 6902 JSON Patch format |
| `rationale` | text nullable | Carried forward from Recommendation when accepted |
| `source_event_id` | UUID nullable | Links reversals to their originating event |

### Indexes

```sql
(household_id, occurred_at DESC)
(entity_type, entity_id, occurred_at DESC)
```

### Retention

Forever. This is a personal-scale single-household app.

### Reversibility

Every change written by an automated subsystem (rule engine, recurrence detection, refund pairing, transfer detection, AI suggestions) is reversible by the user. Reversal writes a new audit event referencing the original via `source_event_id`. History is appended, never mutated.

Replay tooling ships as part of the `audit` module for reconstructing entity state from the event log.
