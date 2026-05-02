# Domain — Recurrences

> Source: `DECISIONS.md` — R2C (Recurring Detection)

---

## Two Kinds of Recurrences

**Detected** — pattern-mined from historical transaction data. The system observes and proposes; the user confirms.

**Declared** — user-defined, future-facing. Can describe a new subscription, a lease not yet started, an anticipated salary raise. May have zero historical data when declared.

A user can flag a single transaction as "start of a new recurring series" to bootstrap a declared recurrence from one observation.

---

## Detected Recurrence Rules

- Group by `(account, normalized_merchant, amount ± tolerance)`.
- Require ≥ 3 occurrences with consistent intervals.
- Supported intervals: weekly, biweekly, monthly, quarterly, annual (all ± a few days tolerance).
- Output: a `RecurrenceCandidate` entity requiring user confirmation.
- **Never auto-promote a candidate to a confirmed recurrence.** HITL always.

---

## Recurrence Fields

| Field | Values / Notes |
|-------|---------------|
| `cadence` | `monthly \| weekly \| biweekly \| semimonthly \| annual \| custom_cron` |
| `expected_amount` | Base expected amount |
| `tolerance` | ± variance allowed for matching |
| `expected_day_of_period` | Which day of the cadence period payment is expected |
| `linked_category` | Optional — auto-assigns category on match |
| `linked_account` | Optional |
| `expected_amount_strategy` | `fixed \| last_n_average \| manual_estimate \| external_signal` |
| `start_date` | When the recurrence began or is declared to begin |
| `end_date` | Optional — when the recurrence ends |
| `paused` | bool — temporarily suspends missed-detection alerts |

---

## Missed / Late Detection

If an expected recurrence has not arrived by `expected_date + tolerance`:

- The calendar shows a "missed" indicator on that date.
- Projections still assume the payment is coming (it counts as an expected future event until dismissed or reconciled).

The indicator **resets** when:
- A matching transaction arrives and is reconciled to the recurrence, OR
- The user manually dismisses the alert.

Dismissed alerts do not re-alert for the same instance of the recurrence.

---

## Deviation Alerts

If a matched transaction differs from `expected_amount` by more than `tolerance`, a deviation alert is raised. Example: "Netflix went from $15.99 to $22.99 — price hike or plan change?"

Deviation alerts route to the HITL queue.

---

## Manual Reconciliation Override

A user can detach a transaction from its recurrence (e.g., "rent was split externally this month") without breaking the series. The series continues; the detached transaction is treated as a one-off.

---

## RecurrenceException

Single-instance overrides that do not break the series. Three flavors:

- **Skip** — this instance does not occur (e.g., "no bill this month").
- **Amount change** — this instance has a different expected amount.
- **Date shift** — this instance lands on a different date.

Each exception is stored as a `RecurrenceException` row referencing the recurrence and the affected period.

---

## Multi-Source Split Detection

When multiple transactions from different internal accounts appear to fund a single spend event, the system flags them:

**Split purchase across cards:** same merchant + same day + amounts summing to a round-ish number or known expected amount → "possible split purchase across accounts."

**Split-funded transfer:** two outbound transfers, same destination, same day → "possible multi-source transfer."

Confirmed groups become **payment groups** in the `transactions` module. For reporting, treated as a single logical spend event. Individual transactions retain per-account attribution.

---

## Lifecycle Rules

- Recurrences are **editable and archivable, never deleted**. `end_date` is mutable.
- Historical data is unaffected by future edits to a recurrence.
- Every transaction carries a `recurrence_id` foreign key for cheap historical lookups (nullable when not part of a recurrence).
