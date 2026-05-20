# WDIAG — Where Did It All Go

**Your household finances, on your server, under your control.**

WDIAG is a self-hosted personal finance application for households that want a complete picture of their money without sending their data to a third party. You run it on your own hardware or VPS. Your transactions, budgets, goals, and debt plans stay in your database — not on someone else's servers, not sold to advertisers, not used to train models.

## Who it's for

WDIAG is built for households — single people, couples, and families — who want:

- **Privacy.** Your financial data is yours. Nothing leaves your server unless you explicitly configure it to.
- **Control.** Self-hosted means you decide when to upgrade, how to back up, and who has access.
- **Household awareness.** Budgets, goals, and visibility work across multiple people sharing finances, with fine-grained control over who sees what.
- **Local AI option.** Get intelligent insights and Q&A against your own data using a local model — no cloud API required.

## How WDIAG is different

| | WDIAG | YNAB / Monarch / Copilot |
|---|---|---|
| Self-hosted | Yes | No |
| Data ownership | You own it | They own it |
| Ads or data selling | Never | Varies |
| Multi-person households | Built-in | Limited |
| Local AI | Supported | No |
| Open source | Yes | No |

## Three ways to start

<div class="grid cards" markdown>

- **Demo** — one command, running in 60 seconds

    ```bash
    docker run -p 80:80 -p 443:443 \
      ghcr.io/justin-cagle/wdiag-aio:latest
    ```

    [Quick Start guide](getting-started/quick-start.md)

- **Production** — full docker-compose stack with Postgres, Redis, and Caddy

    Persistent, multi-user, ready for real use.

    [Installation guide](getting-started/installation.md)

- **Contribute** — the codebase is open

    Python + FastAPI backend, React + TypeScript frontend.

    [GitHub](https://github.com/justin-cagle/where-did-it-all-go)

</div>

## Feature highlights

| Feature | What it does |
|---------|-------------|
| **Accounts** | Track every account — bank, credit card, investment, cash, real estate, crypto. Manual or synced via SimpleFIN. |
| **Transactions** | Full lifecycle: pending → posted → reconciled. Splits, transfer pairing, refund matching, deduplication. |
| **Budgets** | Six methods including zero-based, envelope, 50/30/20, and rolling average. Per-line rollover policies. |
| **Debt Plans** | Avalanche, snowball, or custom payoff strategy. Amortization schedule, interest savings, snowball flow. |
| **Goals** | Eight goal types. Burn-up tracking, completion policies, per-member contribution logging. |
| **Calendar** | Unified view of transactions, projected events, budget periods, goal milestones, and debt due dates. |
| **Projections** | Day-by-day simulation up to 60 months out. Balance curves, net worth trajectory, breach warnings. |
| **AI Insights** | Ask questions about your spending. Anomaly detection and pattern surfacing. Local or cloud providers. |
| **Multi-currency** | Full FX support. Native currency display, home currency aggregation, historical rates via Frankfurter. |
| **Classification** | Categories, tags, and a rules engine that automatically categorizes transactions as they arrive. |
| **Recurrences** | Detected and declared recurring transactions feed the calendar and projection engine automatically. |
| **Households** | Four visibility modes for shared finances. Role-based access, invitation flow, per-member attribution. |

## Current version

WDIAG is in active development, currently at **v0.4.0**. The full feature set is implemented; the project is pre-1.0 and under active hardening. Breaking changes are communicated in the [changelog](changelog.md).

!!! note "Pre-1.0 stability"
    All core features work. The API is not yet considered stable — endpoints may change between minor versions before 1.0. Pin your Docker image tag if stability matters.
