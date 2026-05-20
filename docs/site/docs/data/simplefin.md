# SimpleFIN

## Full setup walkthrough

### 1. Create a SimpleFIN Bridge account

Go to [bridge.simplefin.org](https://bridge.simplefin.org) and create an account. Follow their onboarding to link your financial institutions. SimpleFIN supports most US banks and credit unions — see their site for the current supported institution list.

### 2. Get a setup token

In SimpleFIN Bridge, go to **Apps → Create new connection**. Copy the **setup token**. This is a one-time code — it's exchanged for a permanent access token on connection.

### 3. Connect in WDIAG

Go to **Settings → Connected Accounts** and click **Connect a SimpleFIN account**.

**Step 1 — Get setup token:** paste your setup token and give the connection a name (e.g., "Justin's accounts"). The name is shown in sync status displays throughout the app.

**Step 2 — Map accounts:** WDIAG fetches your accounts from SimpleFIN and asks how to handle each:
- **Create new account** — WDIAG creates an account and imports transactions
- **Map to existing** — links to an account you already created manually
- **Ignore** — skips this account

**Step 3 — Done:** the initial 90-day import starts automatically.

### Error handling during connection

| Error | What it means |
|-------|-------------|
| "Invalid token" | The token wasn't copied completely — get a new one from SimpleFIN |
| "This token has already been used" | Setup tokens are one-time — generate a fresh one |
| "Could not reach SimpleFIN" | Network issue — check your server's internet connection |

## Multiple connections (joint households)

One SimpleFIN Bridge account belongs to one person (one set of bank logins). For a household where two people have accounts at different banks, each person connects their own SimpleFIN Bridge account separately in WDIAG.

Each connection has its own independent **24 requests/day quota**. Two connections in the same household have separate, non-competing quotas.

## Sync intervals and rate limits

Each connection syncs on a configurable schedule. The SimpleFIN quota is 24 requests per Access Token per day.

| Interval | Requests/day | Notes |
|----------|-------------|-------|
| 1 hour | 24 | Uses full quota — no buffer for manual syncs |
| 2 hours | 12 | Frequent; leaves room for manual syncs |
| 4 hours | 6 (default) | Balanced; safe for most users |
| 8 hours | 3 | Conservative |
| 24 hours | 1 | Minimal |

### Approaching limit

When you've used 20 of 24 syncs today, WDIAG shows:

> "Approaching daily sync limit
>
> You've used [N] of 24 syncs today for [credential label]. Your limit resets at approximately [time].
>
> For today's transactions, export a CSV or OFX from your bank and import it below — file imports have no limit."

Manual syncs still work with this warning. They're just noted.

### Hard stop (429)

If SimpleFIN pauses your sync:

> "Sync paused for [credential label]
>
> SimpleFIN has paused syncing until [time] to prevent your account from being flagged for unusual activity. This is enforced by SimpleFIN, not by this app.
>
> For today's transactions, export a CSV or OFX from your bank and import it below."

Syncing automatically resumes after the pause window (approximately 25 hours from the pause trigger). File import is always available.

## Sync status indicators

On the Connected Accounts page and on individual account cards, WDIAG shows the current sync status:

| Status | Meaning |
|--------|---------|
| Active (green) | Syncing normally |
| Warning (yellow) | Approaching daily quota |
| Rate limited (orange) | Paused by SimpleFIN until [time] |
| Error (red) | Last sync failed |
| Disabled (gray) | Sync is manually disabled |

Click any status indicator to navigate to the Connected Accounts settings.

## Supported institutions

SimpleFIN supports most major US financial institutions. See [bridge.simplefin.org](https://bridge.simplefin.org) for the current list — it changes as SimpleFIN adds and maintains connections.

If your institution isn't supported, use [file import](file-import.md) instead.
