# Domain — Classification

> Source: `DECISIONS.md` — R2A (Categories & Tags), R2B (Rules Engine), R2 (Income Source Edge Case)

---

## Classification Pipeline (Strict Order)

The pipeline runs in this exact order on every ingested transaction. Order is deterministic — no step skips ahead or re-runs a previous step.

1. **Transaction-type detection** — pre-rule classifier assigns `transaction_type` (`payroll | refund | transfer | fee | interest | dividend | regular`).
2. **IncomeSource match** — if the transaction matches a known IncomeSource, it is locked to `Income > [sub-category]` regardless of any merchant rules. Merchant rules cannot override this.
3. **User rules** — the rules engine evaluates all active rules in priority order.
4. **Fallback** — if nothing matched, the allocation is assigned to the `Uncategorized` system category.

---

## Categories

**2-level hierarchy:** parent / child. No deeper nesting.

**Household-scoped.** Category trees belong to the household, not to individual users.

**Default tree:** seeded at household creation from an editable template. Template data is copied into normal DB rows — users can edit, rename, or delete anything that is not a system category.

**System categories** — immutable DB rows:

| Name | `system` | `deletable` | `renameable` |
|------|----------|-------------|--------------|
| `Transfer` | true | false | false |
| `Uncategorized` | true | false | false |
| `Income` | true | false | false |
| `Refund` | true | false | false |

System categories are visible in the UI but locked.

---

## Tags

- Flat (no hierarchy).
- Many-to-many: one transaction/allocation can have multiple tags; one tag can apply to many.
- Household-scoped.
- Orthogonal to categories — tags and categories serve different axes of classification.
- "Who spent it" attribution lives on the split allocation via `attributed_to_user_id`, not in the category hierarchy or tags.

---

## Rules Engine

### Shape

```
IF (conditions) THEN (actions) WITH (priority)
```

### Actions

| Type | Fields | Notes |
|------|--------|-------|
| `set_category` | `category_id` | Assigns the transaction/allocation to a category |
| `add_tag` | `tag_id` | Attaches a tag to the transaction |
| `set_merchant_name` | `value: str` | Normalizes the merchant name |
| `set_transaction_type` | `value: str` | Overrides the type-detected `transaction_type` |

### Conditions

| Field | Operators available |
|-------|-------------------|
| `merchant_name` | `equals`, `contains`, `starts_with`, `regex` |
| `description` | `equals`, `contains`, `starts_with`, `regex` |
| `amount` | `amount_equals`, `amount_between` |
| `account` | `equals` |
| `direction` | `equals` (debit/credit) |
| `transaction_type` | `equals` (allows rules to match specific type-detected transactions) |

`regex` is labeled "advanced pattern match" in the UI — not exposed as regex to avoid intimidating non-technical users.

### Priority Resolution

Explicit integer priority, user-editable. **Ties are broken by rule creation date — the older rule wins.**

### Strictness Setting (Household-Level)

Governs behavior across rules, recurrence matching, dedup, and transfer detection:

| Mode | Behavior |
|------|----------|
| `strict` | Multi-match → HITL queue, allocation left uncategorized. **DEFAULT.** |
| `best_guess` | Highest priority wins; allocation flagged for review. |
| `silent` | Highest priority wins; no flag. |

### Per-Rule Modes

- **Auto-apply** — rule fires and applies immediately on ingest.
- **Suggest** — rule fires but flags the transaction for review without modifying the allocation.

### Rule Behavior Rules

- Manual recategorization sets `manually_categorized: true` on the allocation. The rule engine will not re-trigger on that allocation.
- Rule provenance is recorded on every auto-categorized allocation: which rule fired, and when.
- Users can disable any standard (shipped) rule and define new ones.
- Rules run on ingest. Re-running rules on historical transactions is a separate, explicit user-triggered action.

### Rule Test Result

`POST .../rules/{rule_id}/test` returns:

| Field | Notes |
|-------|-------|
| `matching_transaction_ids` | UUIDs of all matching transactions |
| `match_count` | Total matches |
| `sample_count` | Total transactions evaluated |
| `sample_transactions` | First 5 matching transactions as `TransactionSummary` (id, posted_date, description, merchant_name, amount, currency, direction) |

---

## Strictness Setting Scope

The strictness setting applies to all four subsystems:

- Rules engine (multi-match handling)
- Recurrence matching (ambiguous match handling)
- Deduplication (below-confidence-threshold handling)
- Transfer detection (ambiguous pair handling)

---

## IncomeSource

A household-scoped entity that represents a known income stream, attributable to a specific user.

### Fields

| Field | Notes |
|-------|-------|
| `employer_name` | Display name of the payer |
| `attributed_to_user_id` | Which household member receives this income |
| `expected_cadence` | How often payments arrive |
| `expected_amount_range` | Min/max expected per payment |
| `account_id` | Which account receives deposits |
| `variability_model` | `fixed \| range \| historical_distribution` |
| `deposit_split_pattern` | List of `{ account_id, amount_or_percentage }` — for paycheck split-deposit detection |

### Sub-Types

| Sub-type | Description |
|----------|-------------|
| `income-payroll` | Regular salary/wages |
| `income-bonus` | Periodic bonus |
| `income-rsu` | RSU vest events |
| `income-reimbursement` | Expense reimbursements |

These are related but distinct entity types under IncomeSource, not just categories.

### Paycheck Split-Deposit Detection

When a paycheck is split across multiple accounts (e.g., 80% → checking, 20% → savings), the system detects two deposits from the same employer on the same day across accounts owned by the same user.

On first detection, HITL surfaces: "We see two deposits from [EMPLOYER] totaling $X — is this a single paycheck split across accounts?"

On confirmation: the `deposit_split_pattern` is stored. The combined total counts as income for the budget period — no double-counting. Once confirmed, the pattern is remembered. The recurrence detector watches for amount shifts (e.g., user adjusts direct deposit allocation) and flags them.

### Income Splits (Lump-Sum Paychecks)

For paychecks that bundle multiple components (base + overtime + commission + tips), the same split allocation mechanism used for expense transactions applies. Components become separate allocations on the income transaction, each mappable to sub-categories or income types.

### Initial Import Surfacing

During historical import, the recurrence detector surfaces IncomeSource candidates: "We detected recurring credits from [EMPLOYER] — is this employment income? Whose?"
