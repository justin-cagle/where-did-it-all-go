# Emergency Controls

## Read-only mode

**Read-only mode** is a panic switch that immediately stops all writes to the database without taking the application down. Use it when you suspect a sync error is corrupting data, you want to freeze state while investigating, or you need to perform maintenance.

When read-only mode is enabled:

- All users see a persistent warning banner at the top of the app: "Read-only mode — [your reason]. No changes can be made until an administrator disables this mode."
- All write operations return a 503 response immediately
- SimpleFIN sync is paused
- Classification pipeline is paused
- File imports are blocked
- AI insight generation is paused
- Background job queues skip runs and log that they're skipped

What is NOT blocked:
- Viewing all data (reading is fully available)
- Data export
- Admin panel access (you can still disable read-only mode)
- Login and logout

## When to use it

- You see transactions you don't recognize appearing in bulk
- A sync job appears to be creating duplicates or bad data
- You're about to do database maintenance and want to ensure no writes happen
- You suspect a configuration problem and want to halt automated processes while you investigate

## How to enable read-only mode

!!! warning "This affects all users immediately"
    Enabling read-only mode blocks all writes for everyone in the instance and shows a warning banner to every connected user. Use it intentionally.

1. Go to **Admin → Emergency**.
2. Click **Enable read-only mode** (danger-styled, non-filled button — not easy to click accidentally).
3. Complete step-up authentication (re-enter your password or TOTP code).
4. Enter a reason (required, minimum 10 characters). This reason is shown to all users in the banner.
5. Click **Enable read-only mode** (the final confirmation button).

All connected clients see the banner immediately via Server-Sent Events — no page refresh required.

## How to disable read-only mode

1. Go to **Admin → Emergency**.
2. Click **Disable read-only mode**.
3. Complete step-up authentication.
4. The mode is disabled. All connected clients see the banner clear immediately.

## Current state

The Emergency page shows the current state clearly:

**When normal:**
```
● System is operating normally

Read-only mode is not active.
All writes and syncs are enabled.
```

**When active:**
```
⚠ READ-ONLY MODE ACTIVE

Reason: [your reason]
Enabled: [time] by [admin name]
All write operations are blocked.
Syncs are paused.
```
