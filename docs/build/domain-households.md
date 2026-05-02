# Domain — Households & Users

> Source: `DECISIONS.md` — R1A (Multi-User & Household Model)

---

## Household

The top-level organizational unit. All financial data (accounts, transactions, budgets, goals, etc.) is household-scoped.

A household can have one user (single-person deploy) or multiple users (family). The system must degrade cleanly to single-user — no features require multiple users.

---

## Visibility Modes

Selected at household creation. Mutable after creation.

| Mode | Behavior |
|------|----------|
| `fully_shared` | All members see all accounts and transactions |
| `separate_with_joint_view` | Members have private views; a joint view aggregates everything |
| `role_based` | Visibility controlled by role assignments |
| `admin_controlled` | Owner/admin explicitly grants access per member |

---

## Roles

Two separate role axes — do not conflate them:

**App Admin** — sysadmin role. Manages: OIDC configuration, integrations, encryption keys, backups, user invites. Not necessarily a financial participant.

**Household financial roles:**
- `Owner` — full financial access within the household.
- `Member` — financial participant with access per visibility mode.

In a single-person deploy, App Admin and Owner collapse to one human wearing two hats.

---

## Authentication

OIDC handles authentication. The app stores no passwords for OIDC-authenticated users. External IdP handles the auth flow; the app validates the token and issues its own short-lived JWT.

Authentication is **pluggable via `pluggy`**. Auth is the **first committed plugin contract**. Reference implementations shipped:

- **OIDC** — for users with an external IdP (Keycloak, Authentik, etc.)
- **Local auth** — username + password + TOTP, for users without an external IdP

Both are reference plugins, not hardcoded. See [versioning.md](versioning.md) for the pluggy extension point list.

---

## App Admin Actions (Step-Up Auth Required)

The following actions require step-up authentication — re-enter password or TOTP confirmation:

- Adding a household member
- Changing encryption keys
- Exporting full household data

Standard Owner financial actions remain session-authenticated (no step-up).

---

## Session Management

- JWT lifetime: **15 minutes**
- Refresh token: stored as `httpOnly, Secure, SameSite=Strict` cookie (not localStorage)
- Idle timeout: **30 minutes** (configurable, App Admin settable). Implemented as a sliding window on the JWT refresh mechanism — if no API activity within the window, the refresh token is invalidated server-side and the next request forces re-auth.
- Logout invalidates server-side.
- Rate limiting on the auth-receive endpoint.
