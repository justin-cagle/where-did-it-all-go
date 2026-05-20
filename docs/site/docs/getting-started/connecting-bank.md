# Connecting Your Bank

## What is SimpleFIN?

SimpleFIN Bridge is a service that connects to your bank accounts and makes your transaction data available to apps like WDIAG. It acts as a bridge between your bank's systems and your self-hosted app.

Your bank credentials are stored in SimpleFIN — not in WDIAG. WDIAG only receives transaction data via an access token.

SimpleFIN is a paid service (typically a few dollars per month). See [bridge.simplefin.org](https://bridge.simplefin.org) for current pricing.

!!! note "SimpleFIN is optional"
    You can use WDIAG without SimpleFIN by importing transaction files (OFX, QFX, CSV) from your bank. See [File Import](../data/file-import.md).

## Step 1 — Create a SimpleFIN Bridge account

1. Go to [bridge.simplefin.org](https://bridge.simplefin.org) and create an account.
2. Follow their setup process to connect your financial institutions. SimpleFIN supports most US banks and credit unions. See their website for the current list of supported institutions.

## Step 2 — Get your setup token

1. In SimpleFIN Bridge, go to **Apps**.
2. Create a new connection and copy the **setup token**.

The setup token is a one-time code — it's exchanged for a permanent access token when you connect to WDIAG. You can't reuse it, so don't close the page until the connection is saved.

## Step 3 — Connect in WDIAG

1. In WDIAG, go to **Settings → Connected Accounts**.
2. Click **"Connect a SimpleFIN account"**.
3. Paste your setup token.
4. Give the connection a name (e.g., "Justin's accounts" or "Sarah's accounts"). This name is shown in the sync status display.
5. Click **Connect**.

## Step 4 — Map your accounts

After connecting, WDIAG fetches the list of accounts in your SimpleFIN Bridge and asks you what to do with each one:

- **Create new account** — WDIAG creates a new account and imports transactions into it.
- **Map to existing** — if you already created a manual account for this bank account, link them together.
- **Ignore** — skip this account; it won't be imported.

For each account you create, WDIAG pre-fills the name and suggests an account type based on SimpleFIN's data. You can change both before saving.

Click **Save mapping** when done.

## What to expect after connecting

SimpleFIN fetches the **previous day's transactions** from your bank. This is not a limitation of WDIAG — it is how banks share data with third parties. Banks process and share transactions overnight.

> "SimpleFIN provides transactions posted as of yesterday. Banks share the previous day's data overnight — this is how all third-party finance apps work, not a limitation of this app.
>
> For today's transactions, export a CSV or OFX from your bank's website and import it below. There's no limit on file imports."

The first sync imports the last 90 days of history and starts immediately after you save your account mapping.

## Multiple connections (joint households)

Each SimpleFIN Bridge account belongs to one person (one set of bank logins). For a household where two people have separate banks, each person connects their own SimpleFIN Bridge account separately. Each connection has its own independent sync quota.

## Sync schedule

By default, WDIAG syncs your accounts every 4 hours. You can change this per connection:

| Interval | Requests/day | Use case |
|----------|-------------|----------|
| 1 hour | 24 | Maximum freshness; uses full daily quota |
| 2 hours | 12 | Frequent with buffer for manual syncs |
| 4 hours | 6 (default) | Balanced; safe for most users |
| 8 hours | 3 | Conservative |
| 24 hours | 1 | Minimal |

You can also tap **Sync now** at any time to trigger a manual sync. Manual syncs count against your daily quota.

## Data freshness

Even with hourly syncing, the data you see will be from the previous business day. This is a bank-side constraint, not a WDIAG or SimpleFIN limitation. See [Data Freshness](../data/freshness.md) for a full explanation.

## Manual file import as an alternative

If SimpleFIN doesn't support your bank, or if you need today's transactions, export a file from your bank's website and import it. WDIAG supports OFX, QFX, and CSV. See [File Import](../data/file-import.md).
