# Calendar

## What the calendar shows

The calendar is a unified timeline that layers multiple data sources together. At any given date, you can see what actually happened and what is expected to happen.

| Layer | What it shows |
|-------|--------------|
| Posted transactions | Real transactions from your accounts, colored by category |
| Pending transactions | Transactions your bank has seen but hasn't settled, visually distinct from posted |
| Expected recurrences | Upcoming payments based on detected or declared recurring transactions |
| Budget period boundaries | Lines showing where each budget period starts and ends |
| Goal milestones | Markers for goal target dates and intermediate milestones |
| Debt due dates | Payment due dates from your debt accounts |
| HITL queue badges | Indicators on dates where pending decisions exist |

## Confidence on projected events

Future events are not equally certain. The calendar reflects this visually:

- **High confidence** (fixed recurrences with exact amounts, e.g., your rent): solid marker
- **Medium confidence** (variable recurrences with estimated amounts, e.g., utility bill): slightly translucent or dashed
- **Low confidence** (budget-line-implied spending — the system expects spending but not a specific transaction): most translucent

Higher-confidence events are shown more prominently. You're not looking at one version of the future — you're looking at what the data actually supports.

## Clicking future events

Clicking a projected future event opens a detail panel:

- The source recurrence: name, cadence, expected amount
- Confidence level
- Option to edit the underlying recurrence (affects all future instances)
- Option to override just this instance (creates a one-time exception without changing the recurrence)

## Pay period view

In addition to day, week, and month views, the calendar supports a **pay period view** — bounded by your income source's pay cadence. If you're paid every two weeks, the pay period view shows one paycheck-to-paycheck window at a time.

For households with multiple earners, you can choose which income source drives the calendar view, or show all pay period boundaries simultaneously.

## Breach warnings

The calendar and projection engine surface **breach events** — moments when something might go wrong:

- "Checking goes negative on March 15th"
- "Credit card hits limit on April 2nd"

These appear as warnings on the calendar, giving you time to act before the problem occurs.

## Forward projection horizon

The calendar projects forward events up to the configured horizon (default 12 months, configurable up to 60 months). Future months are loaded on demand as you navigate forward — only the visible window is calculated.
