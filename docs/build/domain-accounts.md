# Domain — Accounts

> Source: `DECISIONS.md` — R1B (Account & Transaction Model), R3B (Debts)

---

## Account Types

All account types are first-class from day one.

**Synced accounts** — connected via SimpleFIN or OFX/statement upload. Standard bank accounts, credit cards, investment accounts.

**Manual / non-synced accounts** — cash, vehicles, real estate, valuables, crypto wallets, etc. Used for net worth tracking. No sync required.

Net worth tracking is a committed v1 feature and requires manual accounts to be accurate.

---

## AccountGroup

An `AccountGroup` represents a single underlying bank account that appears as multiple feed entries — the common case being one credit card with a primary cardholder and an authorized user, each generating a separate feed entry.

**What the group represents:** the logical account. All deduplication, budgeting, net worth, and reporting treat the group as a single account. No double-counting of balances.

**Fields on the group:** `primary_holder`, `authorized_users[]`. These live on the group, not on individual feed entries.

**Transaction roll-up:** transactions from any feed entry under the group roll up to the group for all aggregation purposes. Individual feed-level attribution is preserved for per-user spending reports.

**Detection heuristic:** same institution + same balance + similar account name → candidate for grouping. Candidates are surfaced to the HITL queue for user confirmation. Never auto-merged.

---

## DebtAccount

`DebtAccount` is an annotation layer over a regular `Account`. It does not replace the account — it extends it with debt-specific fields.

```
type ∈ { credit_card, loan, line_of_credit, ... }
```

**Multi-balance from day one:** `DebtAccount` is the parent of one or more `DebtBalance` rows. This handles the real-world case of a credit card with multiple APRs (e.g., a 0% balance transfer promotional rate alongside a regular purchase APR).

**APR-with-history:** every `DebtBalance` row tracks its APR as effective-dated rows (see [data-layer.md](data-layer.md) — Versioning). Rate changes are recorded, never overwritten.

### DebtBalance Fields

| Field | Notes |
|-------|-------|
| `principal_balance` | Current balance on this sub-balance |
| `apr` | Current APR (effective-dated) |
| `term` | Loan term if applicable |
| `promotional_period_end` | Date promotional APR expires, if applicable |
| `minimum_payment_strategy` | `fixed_amount \| percentage_of_balance \| from_statement` |
| `statement_day` | Day of month statement closes |
| `due_day` | Payment due day |
| `payoff_target_date` | Optional user-defined payoff goal date |

See [domain-debts.md](domain-debts.md) for the DebtPlan that operates over DebtAccounts.

---

## Balance History

`GET /api/v1/households/{household_id}/accounts/{account_id}/balance-history`

Returns the last 90 days of balance snapshots, one entry per day a reconciliation or balance-update audit event was recorded.

Response: `list[BalanceHistoryPoint]` where each point is `{ date: str (ISO), balance: str (decimal) }`.

Returns `[]` (empty list) — never 404 — when no reconciliation events exist for the account within the window.
