# Accounts

## Account types

WDIAG supports every kind of financial account:

| Type | Examples |
|------|---------|
| Checking | Your everyday bank account |
| Savings | High-yield savings, emergency fund |
| Credit card | Visa, Mastercard, Amex |
| Investment | Brokerage, 401k, IRA |
| Loan | Mortgage, car loan, personal loan |
| Line of credit | HELOC, personal line of credit |
| Cash | Physical cash you want to track |
| Asset | Vehicle, real estate, collectibles |
| Crypto wallet | Any crypto you track manually |

## Synced vs. manual accounts

**Synced accounts** are connected via SimpleFIN Bridge or imported via OFX/QFX/CSV files. Transactions arrive automatically on a schedule.

**Manual accounts** are anything you manage yourself — cash, a vehicle's current value, real estate equity, a 401k you don't sync. You update the balance when you want it reflected in your net worth.

Most people have a mix: synced bank and credit card accounts for automatic transaction tracking, and a few manual accounts for net worth completeness.

## Debt accounts

Any account can be annotated as a debt account. This adds debt-specific fields:

- **APR** — the interest rate. WDIAG stores a history of rate changes, so a balance transfer promotional rate and a regular purchase rate can coexist on the same card.
- **Minimum payment** — how the minimum is calculated: fixed amount, percentage of balance, or pulled from your statement.
- **Statement day** — when the billing cycle closes.
- **Due day** — when payment is due.
- **Payoff target date** — an optional date you want to be debt-free.

A credit card with a 0% balance transfer alongside a 24% regular APR is handled correctly from day one — each sub-balance tracks its own APR and minimum.

See [Debts](debts.md) for the payoff planning features.

## Account groups

An **account group** represents one real-world account that appears as multiple entries in your bank feed — the most common case being a credit card where both the primary cardholder and an authorized user generate separate transaction feeds.

When WDIAG detects two accounts at the same institution with the same balance and similar names, it surfaces them to the HITL queue as a grouping candidate. You confirm; the group is created.

Once grouped, the accounts are treated as one for all reporting, budgeting, and net worth calculations — no double-counting.

## Balance history

Every account tracks a 90-day balance history (one snapshot per day a reconciliation or balance update was recorded). This appears as a chart in the account detail view, letting you see how your balance has changed over time.

## Net worth calculation

Net worth is calculated as the sum of all account balances, converted to your home currency:

- **Assets** (checking, savings, investment, manual asset accounts): added
- **Liabilities** (credit cards, loans, lines of credit): subtracted

Foreign currency accounts are converted using today's exchange rate. If a rate is unavailable, the amount is shown with a `~` prefix indicating an approximation.

## Privacy mode

At any time you can toggle **privacy mode** from the nav bar. This blurs all monetary amounts on screen:

- **Full blur** — amounts shown as `••••`
- **Partial blur** — amounts shown as `$•,•••` (you can see the order of magnitude but not the exact value)

Privacy mode is per-session (not saved to your account) and applies everywhere money is displayed.
