# Projections

## What projections are (and aren't)

Projections are **estimates based on your actual data** — your current balances, your recurring transactions, your budgets, and your plans. They are not predictions of the future. Unexpected expenses, income changes, or life events won't appear in projections until they happen and become data.

Think of projections as: "If everything continues roughly as it has been, and your plans play out as expected, here's what your financial situation looks like."

## How the engine works

WDIAG runs a single deterministic projection engine. Every day from "now" to the projection horizon, it simulates what happens:

1. Starting from your current account balances
2. Applying each expected recurring transaction on its expected date
3. Applying expected budget-line spending
4. Applying debt payment schedules
5. Tracking goal contributions
6. Computing a running balance for each account

The result is a timeline of projected events — one per expected cash flow — with a confidence score for each.

## Balance curve

The balance curve shows a line chart of your account balance(s) over time. You can view:

- Individual account balances
- A combined view (all accounts summed)
- Net worth over time (assets minus liabilities)

Dips and spikes are visible in advance — useful for spotting "the week before paycheck" low points or large annual expenses (car insurance, property tax) before they hit.

## Cash flow view

Cash flow shows income vs. expenses per period — projected forward. A month with a large expected expense shows up as a negative cash flow before it occurs.

## Net worth trajectory

Projects your total net worth forward based on your current trajectory: savings growth, debt payoff, and goal contributions all factor in. Good for long-horizon planning.

## Scenarios: "What if?"

Scenarios let you ask hypothetical questions without changing your actual plans.

*Example: "What if I put $500 extra per month toward my car loan?" — create a scenario, apply the change, compare the resulting balance curve and payoff date to your base plan.*

Scenarios are transient by default (they disappear when you close them). You can save a named scenario to compare later.

Changes you can explore in a scenario:
- Add or remove a recurring transaction
- Change an income amount
- Modify a debt plan's extra payment
- Adjust a goal's contribution rate

## Breach events

The projection engine identifies and surfaces moments where something might go wrong:

- "Checking account goes negative on [date]"
- "Credit card hits its limit on [date]"
- "Emergency fund target reached on [date]"

Breach events appear on the calendar and in a dedicated alerts panel. They give you advance warning — not a real-time notification after the fact.

## Cache and recalculation

Projections are calculated on demand, not pre-computed. The first time you view projections (or after a change to your data), you may see a brief "recalculating" state.

The cache is invalidated whenever your inputs change: new recurrence, edited budget, reconciled debt payment, updated goal contribution rate, or changed FX rates. After any of these, the next projection view triggers a fresh calculation.
