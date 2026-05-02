# Domain — Debts

> Source: `DECISIONS.md` — R3B (Debts)

---

## Model

`DebtAccount` is an annotation layer over a regular `Account` (see [domain-accounts.md](domain-accounts.md)). Multi-balance debt accounts and APR-with-history are supported from day one.

A `DebtPlan` is a payoff strategy applied across a set of `DebtAccount`s.

---

## DebtPlan Fields

| Field | Values / Notes |
|-------|---------------|
| `method` | `avalanche \| snowball \| custom \| none` |
| `monthly_extra_payment` | Additional budget applied beyond minimums |
| `snowball_flow` | bool — when a debt is paid off, redirect its minimum to the next debt. Default: true for both avalanche and snowball. Separable setting. |
| `account_ids[]` | Which DebtAccounts this plan covers |

### Methods

| Method | Description |
|--------|-------------|
| `avalanche` | Pay highest-APR balance first — minimizes total interest paid |
| `snowball` | Pay lowest-balance debt first — maximizes psychological wins |
| `custom` | User-defined priority order across accounts |
| `none` | **No active strategy.** Debt accounts are tracked (balances, minimums, APRs) but no extra-payment recommendations are generated and no payoff schedule is produced. |

---

## Engine Outputs

The debt engine produces:

- Payoff schedule (per-account, per-month): principal / interest split for each period.
- Total interest paid (vs. minimums-only baseline).
- Time-to-debt-free.
- Savings vs. minimums-only.
- Per-month payment recommendations.
- Reactive updates when actual payments deviate from the plan.

---

## Plan-Budget Linkage

The debt engine produces **`Recommendation` objects**. It never directly modifies budgets. Recommendations route through the HITL queue (or auto-apply if the user has enabled that per-source).

See [domain-recommendations.md](domain-recommendations.md).

---

## Versioning

Debt plans are versioned via effective-dated rows (same pattern as budgets — see [data-layer.md](data-layer.md)).

Plan switches mid-stream preserve history. Example: "you switched from snowball to avalanche on [date]" is queryable from the version history.

---

## History Posture

Default is history preservation. Reconciliation of debt payments is an explicit user action, never automatic.
