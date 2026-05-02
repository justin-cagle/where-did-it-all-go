# Domain — Calendar

> Source: `DECISIONS.md` — R4B (Calendar)

---

## Layers

The calendar renders all of the following simultaneously as distinct visual layers:

| Layer | Visual treatment |
|-------|-----------------|
| Posted transactions | Category color, solid |
| Pending transactions | Visually distinct from posted (e.g., lighter, hatched) |
| Expected recurrences | Confidence-graded: fixed = solid marker, variable = dashed/translucent |
| Budget period boundaries | Overlay lines |
| Goal milestones | Markers |
| Debt due dates | Markers |
| HITL queue badges | Indicator on dates with pending decisions |

---

## Views

| View | Notes |
|------|-------|
| Day | Single-day detail |
| Week | 7-day rolling |
| Month | Standard calendar grid |
| Pay period | Bounded by IncomeSource cadence |

---

## Pay Period View

Pay period boundaries are defined per `IncomeSource` using an anchor date + cadence:

```
weekly | biweekly | semimonthly_1_15 | semimonthly_15_eom | monthly | every_n_days | custom
```

**Multi-earner households:** the user selects which income source's pay period drives the calendar view. Alternatively, they can select "union of all" to visualize pay period boundaries from all income sources simultaneously.

Budgets can opt into pay-period boundaries instead of calendar-month. See [domain-budgets.md](domain-budgets.md).

---

## Forward Projection

The calendar renders forward events up to the projection engine's configured horizon (default 12 months). Lazy-loaded per month navigation — only the visible window is rendered.

---

## Click-Through on Future Events

Clicking a future projected event opens a detail panel showing:
- The source recurrence (name, cadence, expected amount)
- Projection confidence level
- Option to edit the underlying recurrence
- Option to override this single instance

Single-instance overrides create a **`RecurrenceException` row** (not a recurrence edit). See [domain-recurrences.md](domain-recurrences.md) — RecurrenceException.
