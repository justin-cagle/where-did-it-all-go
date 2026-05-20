# Goals

## Goal types

WDIAG supports eight goal types. A household can have any number of goals, or none at all.

### Savings target: "Save $X by date Y"

Accumulate a specific dollar amount in a specific account (or a virtual slice of any account) by a target date.

*Example: Save $10,000 emergency fund in your high-yield savings account by December 31st.*

### Purchase: "Save for something specific"

Like a savings target, but tied to a named item or experience. Useful for goals that have a defined price — a vacation, a new laptop, a home repair.

*Example: Save $2,400 for a new laptop by next March.*

### Debt payoff: "Pay off a specific debt"

Links to a debt account from your debt plan and surfaces it in the goals list alongside your savings goals. Gives you a unified view of all financial targets.

*Example: Pay off the car loan by 2027.*

### Emergency fund: "N months of expenses"

Accumulates enough to cover N months of expenses, where N is your choice and "expenses" is computed dynamically from your recent budget actuals. As your spending patterns change, the target adjusts.

*Example: 3-month emergency fund (target updates automatically as your spending changes).*

### Recurring contribution: "Contribute $X/month consistently"

A discipline goal — not about reaching a balance, but about maintaining a contribution habit. Tracks whether you make the contribution each period.

*Example: Contribute $500/month to your brokerage account.*

### Category reduction: "Spend less on X"

Tracks whether you're keeping a category of spending below a monthly target. Motivating for people trying to cut back on dining out, subscriptions, or shopping.

*Example: Keep dining out under $200/month.*

### Net worth: "Reach $X net worth"

A milestone goal for your total net worth (assets minus liabilities), computed across all accounts. Useful as a long-horizon wealth target.

*Example: Reach $500,000 net worth by age 45.*

### Minimum balance: "Never let this account fall below $X"

Ongoing monitoring goal — no end date. Alerts you when a balance drops below the threshold. Good for keeping an emergency buffer in checking.

*Example: Always maintain at least $1,000 in checking.*

## Burn-up chart

For goals with a dollar target and a deadline, WDIAG shows a burn-up chart:

- **Required pace** — the straight line from zero to target, showing what you needed to have contributed by today to be on track
- **Actual progress** — what you've actually contributed

The gap between the two lines tells you at a glance whether you're ahead, on track, or falling behind.

## Goal status

| Status | Meaning |
|--------|---------|
| Ahead | Actual pace exceeds required pace — you'll hit the target early at this rate |
| On track | Actual pace is close enough to required pace |
| Behind | Actual pace is below required pace — you'll miss the deadline at this rate |
| At risk | Significantly behind — the gap is large enough to be concerning |
| Off track | The target date has passed or the shortfall is severe |

## Completion policies

When a goal is reached, what happens next?

| Policy | What it does |
|--------|-------------|
| **Prompt on complete** (default) | Surfaces to the HITL queue: "Goal hit. Archive, extend target, or clone?" |
| **Archive on complete** | Automatically archives the goal when the target is hit |
| **Auto-extend** | Increments the target by a configured amount and continues (good for emergency funds where you always want more) |
| **Auto-clone** | Archives the completed instance and starts a new one with the same parameters (good for annual goals) |
| **Convert to recurring** | Completed goal becomes a recurring contribution discipline goal |

## Logging contributions

Contributions to a goal can come from three sources:

- **Manual** — you log a contribution explicitly (good for cash or non-synced accounts)
- **Tag-driven** — transactions tagged with the goal's tag automatically count as contributions
- **Recurring rule** — a recurring transfer with a goal ID counts automatically each period

## Per-member contribution tracking

In shared households, WDIAG tracks who contributed what to a jointly-funded goal, even when contributions come from a shared funding source. You can see a breakdown like: "You contributed $800, spouse contributed $600, total $1,400 toward $3,000 target."
