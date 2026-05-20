# Recurrences

## What recurrences are

A **recurrence** represents a transaction that happens on a regular schedule — monthly rent, Netflix, your salary, quarterly insurance premium. Recurrences are the foundation of the calendar's future view and the projection engine's estimates.

There are two kinds:

**Detected** — pattern-mined from your transaction history. WDIAG observes your data, notices "there's a $14.99 charge from Netflix every month," and proposes a recurrence. You confirm it.

**Declared** — you create one manually. Useful for recurring expenses that haven't appeared in your history yet (a new lease, a subscription you're about to start) or income that you want to plan around.

## How detection works

WDIAG groups your transactions by account, merchant, and amount (with a small tolerance for variation). If it finds 3 or more occurrences at consistent intervals — weekly, biweekly, monthly, quarterly, or annual — it creates a **recurrence candidate** and puts it in the HITL queue for you to confirm.

WDIAG never auto-promotes a candidate to a confirmed recurrence. You always confirm.

## The HITL queue

When detection surfaces a candidate, you see it in the HITL queue:

- What the recurring transaction appears to be (merchant, amount, cadence)
- The matching transaction history
- Options: confirm as a recurrence, dismiss (not a recurrence), or edit before confirming

This applies to every automated detection — missing payments, deviations, multi-source split detection. You decide; the app proposes.

## Exceptions: skip, amount change, date shift

Recurrences don't always repeat perfectly. WDIAG supports three kinds of one-time exceptions that don't break the series:

| Exception | Use case |
|-----------|---------|
| **Skip** | "No bill this month" — the instance is marked as expected-not-to-arrive |
| **Amount change** | "This month's electric bill will be higher because of the heat wave" |
| **Date shift** | "Payment falls on a holiday, so it'll post on the 2nd instead of the 1st" |

Exceptions are stored individually. The recurrence itself continues unchanged for all other instances.

## Missed payment alerts

If an expected recurring transaction hasn't arrived by its expected date (plus a tolerance window), WDIAG marks it as missed on the calendar. Projections still assume it's coming — it counts as an expected future event until you reconcile it or dismiss the alert.

If a matching transaction arrives and you reconcile it to the recurrence, the missed indicator clears automatically.

## Deviation alerts

If a recurring transaction arrives but the amount differs from what's expected by more than the configured tolerance, a deviation alert routes to the HITL queue:

> "Netflix went from $15.99 to $22.99 — price hike or plan change?"

You can update the recurrence with the new amount (and it will use the new amount going forward) or dismiss the alert if it was a one-time difference.

## How recurrences feed the calendar and projections

Every confirmed recurrence becomes a source of projected future events. The calendar shows these events on their expected future dates. The projection engine uses them when calculating your future balance curve.

This is why confirming your recurring transactions promptly matters — the more accurately your recurrences reflect reality, the more useful your projections are.
