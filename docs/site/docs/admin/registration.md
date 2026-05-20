# Registration Control

Registration controls determine whether new users can create accounts and how many can exist.

## ALLOW_REGISTRATION

Controls whether the `/register` page is accessible to unauthenticated users.

- `false` (default) — registration is closed. The register link is hidden. Only users with a valid invitation link can create accounts.
- `true` — anyone can register at `/register`.

**Invited users bypass this setting entirely.** If a user has a valid invitation link, they can always create an account regardless of `ALLOW_REGISTRATION`.

## REGISTRATION_LIMIT

Only meaningful when `ALLOW_REGISTRATION=true`. Sets the maximum number of active (non-deleted) user accounts allowed.

- Unset: unlimited
- Set to N: once N active users exist, further registrations are blocked (403, "Registration full")

Invited users bypass this limit. Admins bypass this limit.

## UNASSIGNED_ACCOUNT_TTL_DAYS

When `ALLOW_REGISTRATION=true`, someone might register and then never get assigned to a household (e.g., they found your instance but you're not expecting them). This setting controls how long unassigned accounts survive before automatic cleanup.

- Default: 7 days
- After TTL expires, unassigned accounts (no household, no pending invite) are hard-deleted by a daily cleanup job

## Registration behavior matrix

| ALLOW_REGISTRATION | Registration Limit | Invite? | Result |
|--------------------|-------------------|---------|--------|
| false | any | No | Blocked — register page hidden |
| false | any | Yes | Allowed — invite is the gate |
| true | Not set | Any | Allowed |
| true | N, active users < N | Any | Allowed |
| true | N, active users >= N | No | Blocked — "Registration full" |
| true | N, active users >= N | Yes | Allowed — invite bypasses limit |

## What happens after registration

**Invited user:** immediately joins the household they were invited to and goes to the dashboard. No waiting.

**Open registration (no invite):** account is created without a household. User sees the waiting page:

> "Account created — waiting for access
>
> Your account has been created. A WDIAG administrator will assign you to a household. You'll receive a notification when access is granted."

The admin panel shows a badge for unassigned users. An admin assigns the user to a household from the Users page. The user is notified and redirected to onboarding.

## Changing settings without redeploying

Registration settings can be changed from the admin panel at `/admin` — the overview page has a Registration panel with inline edits. You don't need to edit `.env` and restart.

Settings changed in the admin panel take effect immediately and persist in the database (overriding env vars).
