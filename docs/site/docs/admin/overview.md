# Admin Panel

## What the admin panel is for

The admin panel is for **instance management** — not financial data. An App Admin manages the WDIAG installation: who can register, which users exist, system health, SMTP configuration, and backups.

Financial data (transactions, budgets, goals, accounts) is never visible in the admin panel. App Admin is an infrastructure role, separate from household financial participation.

## How to access it

Navigate to `/admin`. The admin panel has a separate visual design from the main app — always dark, always clearly marked as admin territory.

The sidebar link to Admin appears in the main app only if your account has `is_app_admin = true`. If you see "Admin access required" when navigating to `/admin`, your account isn't an admin.

## Who can access it

Only users with `is_app_admin = true`. This is set at bootstrap (the first admin account), or promoted via the CLI or by an existing admin.

## Admin panel vs. household settings

These are different. Easy to confuse — here's the distinction:

| Admin panel (`/admin`) | Household settings (`/settings/household`) |
|------------------------|-------------------------------------------|
| Instance-level | Household-level |
| All users, all households | Your household only |
| Registration control, SMTP, backup | Members, visibility mode, home currency |
| App Admin only | Household Owner |

## Overview page walkthrough

The admin overview (`/admin`) is the landing page. It shows:

**Users card**
- Active user count
- Unassigned users (accounts without a household — warning if > 0)
- Registration status: Open (N/limit) or Closed
- Admin count

**Households card**
- Total households
- Total members across all households

**System card**
- Worker fast pool: Running/Stopped
- Worker slow pool: Running/Stopped
- Pending jobs and failed jobs in the last 24 hours
- Database size
- Last backup: relative time + status (warning if over 24 hours or failed)

**Notifications panel**
- Unread admin notifications: new unassigned registrations, backup failures, worker pool issues, registration limit reached
- Mark individual or all as read

## Admin sidebar navigation

| Page | What it's for |
|------|--------------|
| Overview | Dashboard summary |
| Users | List, assign, promote, delete users |
| Households | List households and their members |
| System | Worker pools, failed jobs, database stats, Redis, migration state |
| SMTP | Configure email delivery |
| Backup | Backup configuration, run history, manual trigger |
| Emergency | Read-only panic switch |
