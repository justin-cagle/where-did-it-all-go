# Household Overview

## What a household is

A **household** is the top-level organizational container in WDIAG. All financial data — accounts, transactions, budgets, goals, debt plans — lives inside a household.

WDIAG works for a single person or for a multi-member household (couple, family). In v1, one user belongs to one household. A household can have multiple members.

## Roles

There are three distinct roles in WDIAG. They are not on a single ladder — they serve different purposes.

### App Admin

The instance administrator. Manages the WDIAG installation: registration settings, SMTP configuration, backups, user accounts, and system health. An App Admin may or may not be a financial participant in any household.

In a typical single-household self-hosted setup, one person wears both the App Admin hat and the Household Owner hat.

### Household Owner

Full financial access within the household. Can invite new members, manage household settings, change visibility mode, and see all financial data regardless of visibility mode.

### Household Member

A financial participant with access determined by the household's visibility mode. In fully_shared mode, members see everything. In other modes, they may have restricted visibility.

## What each role can do

| Action | App Admin | Household Owner | Member |
|--------|-----------|----------------|--------|
| Manage SMTP, backup, registration | Yes | No | No |
| View/delete any user | Yes | No | No |
| Access admin panel | Yes | No | No |
| Change household visibility mode | No | Yes | No |
| Invite household members | No | Yes | No |
| See all accounts/transactions | No | Yes | Depends on visibility mode |
| Add/edit accounts | No | Yes | Yes |
| Create/edit budgets | No | Yes | Yes (own budgets) |
| View transactions | No | Yes | Depends on visibility mode |

## Single-person deployments

WDIAG works cleanly with one user in one household. No features require multiple household members. If you're deploying for yourself, you're the App Admin and the Household Owner — the distinction just isn't very meaningful when it's just you.
