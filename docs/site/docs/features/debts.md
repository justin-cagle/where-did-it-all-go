# Debts

## What is a debt plan?

A **debt plan** is a payoff strategy applied across your debt accounts. It tells you: given how much extra money you can put toward debt each month, which debts to pay down first, and when you'll be done.

Debt accounts (credit cards, loans, lines of credit) are tracked automatically — balances, APRs, minimum payments, statement dates. A debt plan takes that data and generates a schedule.

## Payoff methods

### Avalanche: Pay highest APR first

Mathematically optimal. Extra payment goes to the debt with the highest interest rate. Once that's paid off, the extra payment (plus its freed minimum) moves to the next-highest-rate debt.

*Example: $5,000 credit card at 24% APR vs. $15,000 car loan at 6% APR.*
*Avalanche: attack the credit card first. You pay more interest to the car loan in the short term, but save significantly more in total interest over time.*

### Snowball: Pay lowest balance first

Psychologically motivating. Extra payment goes to the smallest balance. Paying off a debt completely — even a small one — provides a win that can maintain momentum.

*Example: $5,000 credit card at 24% APR vs. $15,000 car loan at 6% APR.*
*Snowball: attack the credit card first (it's the smaller balance). In this case, the methods agree — but if the car loan had a $3,000 balance, snowball would attack it first even though the card has a higher APR.*

### Custom: Your priority order

You define the order. Drag debts into the priority sequence you want. The extra payment follows your order.

### None: Tracking only

Track debt balances, APRs, and minimums without generating a payoff strategy. No schedule, no recommendations — just visibility.

## Snowball flow

**Snowball flow** is on by default for both avalanche and snowball methods. When you pay off a debt, its minimum payment doesn't disappear — it gets redirected to the next debt in the priority order.

*Example: You're paying $200/month on a $3,000 card (minimum $50 + $150 extra). Card is paid off. Snowball flow: the full $200 now applies to your next debt — $150 extra plus the freed $50 minimum.*

This is what turns debt payoff into an accelerating process. You can turn snowball flow off if you'd rather keep the freed minimums as spending money.

## Amortization table

The debt plan generates a month-by-month schedule showing, for each debt account, each month:

- Principal paid
- Interest paid
- Remaining balance
- Extra payment applied (if any)

This lets you see exactly how each debt will be paid down under your plan.

## Comparison view

The comparison view shows two scenarios side by side:

- **Your plan** — with the extra payment and chosen method
- **Minimums only** — what happens if you only ever pay the minimum

The difference shows: total interest saved, months shaved off, and time to debt-free.

## Recording payments

When you make a payment on a debt account, it's reflected automatically if the account is synced via SimpleFIN. For manual accounts, you record the payment yourself.

Payments are reconciled against the debt plan. If you pay more or less than the plan recommends, the schedule recalculates.

## How debt plans connect to budgets

The debt engine generates **recommendations** for budget lines — "add a budget line for $350/month toward debt" — routed through the HITL queue. You review and accept (or not). The debt plan never directly edits your budget.
