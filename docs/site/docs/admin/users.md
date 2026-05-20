# User Management

## Listing users

The Users page (`/admin/users`) lists all users with filters:

- **Search** by email or display name
- **Toggle** to show All / Unassigned / Admins only

Each user row shows: name, email, admin badge (if applicable), household membership(s) with role, last seen, and a TTL countdown if they're unassigned and approaching deletion.

## Assigning a user to a household

Unassigned users appear with a warning indicator. To assign one:

1. Click **Assign to household** on the user row (or from the user detail page).
2. Choose a household from the dropdown.
3. Choose a role: Member or Owner.
4. Confirm (step-up authentication required).

The user is immediately added to the household. They receive an in-app notification and an email (if SMTP is configured). If they're on the waiting page, they're redirected automatically via Server-Sent Events — no page refresh needed.

## Promoting and demoting admins

To promote a user to App Admin:

- Click **Promote** on the user row. Requires step-up authentication.

To demote an admin:

- Click **Demote** on the user row. Requires step-up authentication.
- Blocked if the target is the last admin — you cannot remove the last admin account.

Via CLI:

```bash
docker compose exec app uv run python -m app.admin promote-admin --email=user@example.com
docker compose exec app uv run python -m app.admin demote-admin --email=user@example.com
```

## Force logout

**Force logout** revokes all active sessions for a user. They'll be signed out on all devices immediately and will need to log in again. Useful if a device is lost or a session looks suspicious.

This does not delete the account or change any data.

## Deleting a user

**Warning:** User deletion is permanent and cannot be undone.

When a user is deleted:
- All their active sessions are revoked
- Their household memberships are removed
- Their "attributed to" tag on split allocations is removed (transactions remain, just lose the user attribution)
- Their user account is hard-deleted
- An audit log entry is written

The delete button is on the user detail page. It requires step-up authentication and a confirmation dialog that shows: "This will permanently delete [name]'s account. Transaction attribution will be removed. This cannot be undone."

Deletion is blocked if the user is the last App Admin.

## Unassigned user cleanup

WDIAG runs a daily cleanup job that hard-deletes accounts where:
- No household membership exists
- No pending invitation exists (invited users waiting to accept are exempt)
- The account was created more than `UNASSIGNED_ACCOUNT_TTL_DAYS` days ago (default 7)

The TTL countdown appears on unassigned user rows in the admin panel. If you want to keep an unassigned account, assign it to a household before the TTL expires.
