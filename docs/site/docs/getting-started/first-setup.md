# First Setup

After installing WDIAG, this guide walks you through the initial configuration.

## Creating the admin account

The first admin account is created via bootstrap environment variables. Set these in your `.env` file before the first start:

```bash
BOOTSTRAP_ADMIN_EMAIL=admin@yourdomain.com
BOOTSTRAP_ADMIN_PASSWORD=your-strong-password
```

WDIAG reads these once on startup when the database is empty, creates the admin account, and never reads them again. You can remove them from `.env` after the first start — they have no effect once users exist.

!!! warning "Change the default password"
    If you are using the AIO demo image, the default password is `admin`. Change it immediately in **Settings → Profile**.

## Logging in for the first time

Navigate to your instance URL. Log in with the admin credentials you set.

## Admin panel overview

After logging in, you will see the admin panel (`/admin`). The admin panel is separate from the main app — it's for instance management, not financial data.

From here you can:

- See active users, unassigned accounts, and system health
- Configure SMTP for email delivery
- Set up backup
- Manage registration settings

Click **"← Back to app"** in the admin sidebar to return to the main application.

## Creating your household

In the main app, you will be prompted to create a household. A household is the top-level container for all financial data — accounts, transactions, budgets, and goals all live inside it.

**Name** — give it a name like "Smith Family" or "My Finances."

**Visibility mode** — controls what household members can see. For a single person or a couple who wants full transparency, choose **Fully Shared**. See [Visibility Modes](../households/visibility-modes.md) for a detailed comparison.

**Home currency** — the currency all totals, net worth, and budgets roll up to. This can be changed later, but doing so triggers a full recalculation of historical data.

## Inviting household members

If other people share finances with you, invite them via **Settings → Household → Invite Member**.

Enter their email address and select a role (Member or Owner). If SMTP is configured, they will receive an email. If not, you will get a link to share manually.

See [Inviting Members](../households/inviting-members.md) for the full flow.

## Setting home currency

Home currency is set when you create your household. To change it later:

1. Go to **Settings → Household**
2. Find the Home Currency selector
3. Choose your currency and confirm

Changing home currency triggers a background recalculation of all budget actuals, goal progress, and projections using historical exchange rates. Figures will be marked as "recalculating" until the process completes.
