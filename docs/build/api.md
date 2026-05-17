# API

> Source: `DECISIONS.md` — R8 (API Surface), R5 (Extensibility)

---

## Style

**REST with OpenAPI.** FastAPI auto-generates the spec. No GraphQL. No tRPC.

**Public API parity.** The API the frontend uses is the same API plugins use, scripts use, and external integrations use. There is no internal/external split.

---

## URL Structure

All routes are household-scoped at the URL level. Versioned from day one.

```
/api/v1/households/{household_id}/accounts
/api/v1/households/{household_id}/accounts/{account_id}/transactions
/api/v1/households/{household_id}/budgets
/api/v1/households/{household_id}/budgets/{budget_id}/lines
/api/v1/households/{household_id}/recommendations
/api/v1/households/{household_id}/calendar?start=...&end=...&view=pay_period
/api/v1/households/{household_id}/projections?horizon_months=12&scenario_id=...
/api/v1/households/{household_id}/events   ← SSE endpoint
```

API paths with UUIDs appear only in network requests (over TLS). The frontend SPA uses friendly client-side routes (`/accounts`, `/budget`); UUIDs never appear in the browser URL bar.

---

## Authentication

OIDC redirect → app receives token → validates → issues:
- Short-lived JWT (15 min).
- Refresh token.

Both stored as `httpOnly, Secure, SameSite=Strict` cookies. **Never localStorage.**

Logout invalidates server-side.

Rate limiting on the auth-receive endpoint.

**Idle timeout:** 30 minutes (default), configurable by App Admin. Implemented as a sliding window on the JWT refresh — if no API activity within the window, the refresh token is invalidated server-side and the next request forces re-auth.

### Auth Endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/v1/auth/sessions` | List active refresh tokens for the current user. Returns `id`, `created_at`, `last_used_at`, `user_agent`. |
| `POST` | `/api/v1/auth/change-password` | Verify current password, hash new password, revoke all refresh tokens. Rate-limited (5/min). Body: `{ current_password, new_password }`. Returns 204. |

---

## Real-Time Updates (SSE)

Endpoint: `GET /api/v1/households/{household_id}/events`

Server-Sent Events, filtered server-side by household membership.

Event types include:
- `recommendation.created`
- `transaction.ingested`
- `sync.completed`
- `recurrence.detected`
- (others as subsystems emit them)

SSE events trigger TanStack Query cache invalidations on the frontend.

---

## Offline Behavior

**Read-only offline.** The service worker caches:
- App shell (HTML/CSS/JS bundle)
- Most recent API responses for: accounts, recent transactions, current budget, active goals, current recommendations
- Static assets

**No write queue.** Mutations attempted while offline receive a clear error and "try again when connected" message.

---

## Pagination

Cursor-based: `?cursor=...&limit=50`. Not offset-based.

The frontend can present this as either traditional paginated navigation (page buttons) or infinite scroll — user preference per list. Both use the same cursor-based API underneath.

---

## Conventions

| Convention | Implementation |
|-----------|---------------|
| Filtering | Structured query params; complex queries get dedicated endpoints |
| Errors | RFC 9457 Problem Details — every error has `type`, `title`, `status`, `detail`, `instance` |
| Idempotency | Optional `Idempotency-Key` header on mutation endpoints |
| Caching | ETags / `If-None-Match` on cacheable read endpoints |
| Bulk ops | Explicit endpoints (e.g., `POST /transactions/bulk-categorize`) |

---

## Programmatic Access Tokens

Two types, separate from session cookies:

| Type | Notes |
|------|-------|
| Personal access tokens | Per-user, for scripts and personal automation |
| Service tokens | Headless integrations (no user context) |

Both are: scoped (declared permission set), revocable, and fully audited.
