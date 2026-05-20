# Budgets

## What is a budget period?

A budget covers a span of time — a **period** — and tracks planned vs. actual spending within that period. The most common period is monthly, but WDIAG also supports weekly, biweekly, semimonthly, annual, and custom periods.

Budgets can also align to your **pay period** instead of calendar months. If you're paid every two weeks, your budget can start and end on your paydays instead of the 1st and 31st.

## Budget methods

WDIAG supports six budget methods. Each household can have multiple budgets running simultaneously — for example, a joint household budget and individual personal budgets.

### Zero-based: "Every dollar assigned"

Every dollar of expected income is assigned to a category before the period starts. Income minus all budget lines equals zero — nothing is left unallocated.

This is the most intentional method. It takes effort to set up but gives you precise control over where your money goes.

*Example: You expect $5,000 income. You assign $1,800 to housing, $600 to groceries, $300 to dining, $400 to transportation, and so on until you've allocated all $5,000.*

### Envelope: "Spending pots"

Each category has a fixed amount per period — its "envelope." Spending against an empty envelope triggers a warning (or blocks, depending on your settings). Unspent amounts can roll forward to next month if you configure rollover.

*Example: Dining envelope is $300. Once you've spent $300 eating out, the envelope is empty. Any additional dining purchase triggers a notification.*

### 50/30/20: "Automatic split"

Categories are tagged as **needs** (50%), **wants** (30%), or **savings** (20%). WDIAG enforces aggregate spending ratios — it doesn't care what you spend within "needs" as long as the total stays under 50% of income.

This is the simplest method for people who want guardrails without micromanaging every category.

### Rolling average: "Auto from history"

Budget line amounts are automatically set from your actual spending over the last N periods (default 3). No manual line entry required. The budget self-updates each period based on your history.

Good for: getting a realistic picture of what you actually spend, without setting aspirational numbers you'll never meet.

### Percentage-based: "Income percentages"

Lines are defined as percentages of income, not absolute amounts. Each period, WDIAG multiplies your income by the percentages to get the dollar amounts.

*Example: Groceries = 12% of income. If you earn $5,000, your groceries budget is $600. If you earn $6,000 next month, it's $720.*

### Manual: "Full control"

Planned amounts are advisory only — no enforcement. WDIAG shows you planned vs. actual, but doesn't warn or block. Good for tracking purposes when you want visibility without constraints.

## Budget lines and categories

A budget line is one category (or category + tag combination) within a budget, with a planned amount for the period.

Lines are additive within a budget period. If you have a "Groceries" line and a "Dining" line, they track separately. The budget overview shows you where you stand on each line.

## Rollover policies

Different lines in the same budget can have different rollover policies — what happens to unspent money at the end of the period.

| Policy | What happens at period end |
|--------|--------------------------|
| **None** | Unspent resets to zero. This period's allocation is this period's allocation. |
| **Accumulate** | Unspent carries forward indefinitely. Save $50 this month, have $50 extra next month. Classic envelope behavior. |
| **Accumulate (capped)** | Carries forward up to a maximum. Prevents the balance from growing forever — good for things like a car maintenance fund. |
| **Debt carry** | Overspending carries as a negative into the next period. If you overspend by $30 this month, next month's effective allocation is $30 less. |
| **Reset on overspend** | If you overspend, next period's allocation resets to zero. A stronger penalty than debt carry. |

## Expected income strategies

How WDIAG determines your expected income for budget calculations:

| Strategy | How it works |
|----------|-------------|
| **Fixed** | You declare a flat amount per period. |
| **From income sources** | Sums your declared income sources (payroll, etc.) for the period. |
| **Last period actual** | Uses what actually came in last period. |
| **Rolling average** | Averages the last N periods (default 3). Good for variable income. |
| **Manual per period** | You enter the amount at the start of each period. No auto-calculation. |

## Reading budget status

Each budget line shows one of three statuses based on actual spending vs. planned:

- **Under** — actual spending is below the planned amount with room to spare.
- **On track** — actual spending is close to the expected pace for the period.
- **Over** — actual spending has exceeded the planned amount.

## Budget versioning

Editing a budget creates a new version with an effective date. Each budget period uses the version that was active on its start date.

This means: changing your grocery budget from $600 to $500 in March doesn't rewrite February's budget history. February still shows $600 planned, March and beyond show $500. Your historical records are never altered.
