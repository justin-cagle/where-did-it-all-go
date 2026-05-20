# Data Freshness

## Why data isn't real-time

WDIAG shows your bank data from the **previous business day**. This is not a limitation of WDIAG or SimpleFIN — it is a fundamental constraint of how banks share data with third parties.

Banks process transactions overnight and make them available via data-sharing APIs the following day. There is no path to real-time transaction data through SimpleFIN or any other bank aggregator without a direct API relationship with each bank (which most banks don't offer to consumers or small developers).

This is how all third-party finance apps work — whether WDIAG, Mint, YNAB, Monarch, or any other app using the same bank data infrastructure.

> "SimpleFIN provides transactions posted as of yesterday. Banks share the previous day's data overnight — this is how all third-party finance apps work, not a limitation of this app.
>
> For today's transactions, export a CSV or OFX from your bank's website and import it below. There's no limit on file imports."

## SimpleFIN data

SimpleFIN syncs on your configured schedule (default: every 4 hours). Each sync pulls data that your bank has made available. On most days, that data reflects transactions through the previous business day.

- Same-day transactions will not appear until the following day at the earliest
- Weekends and holidays may cause a day or two of additional delay
- First sync imports the last 90 days of history

## File import

File imports are not subject to SimpleFIN's data latency. When you export a CSV or OFX from your bank's website, you typically get transactions through today (or even through the current business day).

Use file import when:
- You need to see today's transactions right now
- SimpleFIN doesn't support your bank
- You're importing historical data

There is no limit on file imports.

## Pending vs. posted transactions

Banks distinguish between **pending** and **posted** transactions:

- **Pending** — the transaction has appeared (often immediately after a card swipe) but hasn't settled
- **Posted** — the transaction has settled; the amount is final

WDIAG imports pending transactions when SimpleFIN includes them, marked as pending status. Some banks hold back pending transactions from the API feed until they post. Either way, a transaction's amount may change slightly between pending and posted (common for gas stations, restaurants with tip, etc.).

## When bank data updates

Different banks make data available at different times. Most US banks post previous-day transactions sometime in the early morning hours. Some banks update multiple times per day. A few banks have 2–3 day settlement delays for certain transaction types.

If you notice your transactions are consistently behind by more than a day, this is typically a bank-side behavior, not a WDIAG issue. File import is the reliable path to same-day data regardless of your bank's update schedule.
