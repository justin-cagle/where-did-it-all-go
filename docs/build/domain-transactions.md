# Domain — Transactions

> Source: `DECISIONS.md` — R1B (Account & Transaction Model), R2 (Income Source Edge Case)

---

## Transaction Lifecycle

State machine: `pending → posted → reconciled`

Reconciliation is an explicit user action. The system does not auto-reconcile.

---

## Splits (Allocations)

Splits are **allocations**, not child transactions. The transaction itself remains atomic — one row, one amount. Splits are a tagging/categorization layer applied over the transaction.

Rules:
- Sum of all split allocations must equal the transaction amount.
- An "uncategorized remainder" allocation is allowed for partial splitting.
- A transaction with no splits gets an implicit single allocation to its assigned category.
- Budgets and category reports aggregate over split allocations, not transactions directly.

### Split Allocation Fields

| Field | Notes |
|-------|-------|
| `amount` | Portion of the transaction |
| `currency` | Paired with amount |
| `category_id` | Category assigned to this portion |
| `tag_ids[]` | Tags applied to this portion |
| `attributed_to_user_id` | Defaults to account's `primary_holder` |
| `manually_categorized` | `bool` — if true, rule engine will not re-trigger on this allocation |
| `rule_id` | Which rule fired (provenance); nullable if manually set |
| `rule_fired_at` | When the rule fired; nullable |

---

## Transaction Type Field

Every transaction has a `transaction_type` field populated by a pre-rule classifier (runs before user rules):

```
payroll | refund | transfer | fee | interest | dividend | regular
```

Classifier signals: ACH SEC code (when present), description tokens (`PAYROLL`, `DIR DEP`, `DIRDEP`, `DD`, `SALARY`, `WAGES`, `EARNINGS`), recurrence cadence/stability, OFX `NAME`/`PAYEEID` fields, amount magnitude vs. account history.

This field feeds the classification pipeline. See [domain-classification.md](domain-classification.md).

---

## Transfer Pairing

When a transfer is detected, the user is asked whether it is:
- **Internal** — links to an internal account (e.g., checking → savings).
- **External** — links to nothing (e.g., wire to an external party).

Detection is heuristic. Manual override always available. Confirmed transfers are assigned to the `Transfer` system category.

---

## Refund Pairing

Pairing criteria: same merchant, opposite sign, within N days, and the original debit ≥ the refund credit (handles partial refunds). Pairs net out cleanly in spending reports. Mechanically similar to transfer pairing — detected heuristically, surfaced to HITL.

---

## Payment Groups

When multiple transactions from different accounts constitute a single logical spend event, they are linked as a **payment group**. Two flavors:

**Split purchase across cards:** same merchant + same day + amounts summing to a round-ish number or known expected amount → "possible split purchase across accounts."

**Split-funded transfer:** two outbound transfers, same destination, same day → "possible multi-source transfer."

On HITL confirmation: a payment group is created linking the transactions. For reporting, the group is treated as a single logical spend event. Individual transactions retain their per-account attribution for reconciliation.

---

## Deduplication

Layered strategy:

1. **Source-provided ID** — prefer SimpleFIN ID or OFX `FITID` when present. Exact match.
2. **Fuzzy match** — `account + amount + date ± N days + normalized description`. Scored with a confidence value.
3. **Below confidence threshold** → manual merge queue (HITL). Never auto-merge below threshold.

**Source merge policy (same period, two sources):** SimpleFIN wins on the canonical record. Statement data is reference-only.

---

## FX (Foreign Currency Transactions)

Multi-currency is supported from day one. See [data-layer.md](data-layer.md) for column rules.

**Per-transaction FX snapshot:** the exchange rate at transaction time is stored on the transaction row and is immutable. This is the historical truth — "how many USD did I spend that day?"

**Daily rate table:** populated lazily (only when a currency exists in an account or transaction). Enables current revaluation of foreign-currency balances and goals. Daily rates only — no intraday.

**For projections:** foreign-currency amounts project flat by default (no rate movement assumed). This default is user-configurable per recurrence.

The household has a `home_currency` field; all net worth rollups convert to this currency using the daily rate table.
