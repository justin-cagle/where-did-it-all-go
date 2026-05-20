# Features Overview

## How the pieces connect

WDIAG is built around a central data flow. Every feature either puts data in, makes sense of it, or projects it forward.

```
Bank / File Import
       │
       ▼
   Ingest Layer
  (SimpleFIN, OFX, CSV)
       │
       ▼
  Transactions
  (deduplicated, state-tracked)
       │
       ▼
  Classification
  (type detection → income sources → rules → fallback)
       │
       ├──► Budgets (spending tracked by category)
       │
       ├──► Goals (progress toward targets)
       │
       ├──► Debt Plans (payoff scheduling)
       │
       ├──► Recurrences (pattern detection)
       │         │
       │         ▼
       └──► Projections (day-by-day simulation)
                 │
                 ▼
             Calendar
          (unified timeline)
                 │
                 ▼
           AI Insights
       (patterns, anomalies, Q&A)
```

## What each feature does

| Feature | What it does |
|---------|-------------|
| [Accounts](accounts.md) | Tracks every financial account. Synced via SimpleFIN or managed manually. Supports bank accounts, credit cards, investments, and assets like real estate or vehicles. |
| [Transactions](transactions.md) | The raw data — every money movement. WDIAG tracks state (pending → posted → reconciled), allows splitting across categories, pairs transfers and refunds, and deduplicates overlapping imports. |
| [Classification](classification.md) | The rules engine that automatically categorizes transactions as they arrive. You define the rules; the engine runs deterministically every time. |
| [Recurrences](recurrences.md) | Detected from patterns in your transaction history (Netflix, rent, salary). Feed into the calendar and projections so future events are visible before they happen. |
| [Budgets](budgets.md) | Plans for how to allocate your money each period. Six methods available. Multiple budgets per household are supported. |
| [Debts](debts.md) | Tracks loans and credit cards with APRs. Generates a payoff schedule using avalanche, snowball, or custom priority. Shows total interest paid and time to debt-free. |
| [Goals](goals.md) | Eight goal types — from saving for a purchase to maintaining a minimum balance. Burn-up chart tracks your actual pace vs. what's needed to hit the target on time. |
| [Calendar](calendar.md) | Unified timeline showing posted transactions, projected future events, budget period boundaries, goal milestones, and debt due dates. |
| [Projections](projections.md) | Day-by-day simulation of your financial future based on your balances, recurrences, and plans. Balance curves, net worth trajectory, breach warnings. |
| [AI Insights](ai-insights.md) | Optional layer that observes your data and surfaces anomalies, patterns, and answers to natural language questions. Works with local or cloud AI providers. |

## The HITL queue

Throughout WDIAG, you will encounter the **HITL queue** (Human-In-The-Loop). This is the inbox for all decisions that the app detected but needs your confirmation on:

- A possible recurring transaction detected
- A possible duplicate transaction from overlapping imports
- A possible transfer pair between two accounts
- A possible refund match
- A classification suggestion (if rules are in "suggest" mode)

The philosophy is: WDIAG observes and proposes; you decide. Nothing is automatically applied without your sign-off unless you explicitly enable auto-apply for a specific suggestion type.
