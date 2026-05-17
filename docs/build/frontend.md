# Frontend

> Source: `DECISIONS.md` — R10 (Frontend)

---

## Architecture Rule: No Business Logic in Components

Business logic lives in `domain/` modules — pure TypeScript, no React, no DOM dependencies. TanStack Query hooks call into domain modules. React components are rendering + event wiring only.

This is the load-bearing rule for keeping React Native viable in v2/v3. Estimated logic/hooks/types reuse with RN: 50–70%. UI code reuse: 0%.

---

## State Management

| State kind | Tool |
|------------|------|
| Server state (cache, refetch, mutate, optimistic update) | TanStack Query |
| Cross-cutting client state | Zustand |

SSE events trigger TanStack Query cache invalidations. See [api.md](api.md) — Real-Time Updates.

---

## Component Library

**shadcn/ui** is the foundation. Components are owned source (copy-paste from CLI), not a dependency. Customizable at the code level.

One exception: **Mantine `@mantine/dates`** for full month/agenda calendar views, if shadcn's calendar component is insufficient.

---

## Icons

**Lucide** (`lucide-react`) is the primary icon library. Animated variants from lucide-animated.com where appropriate. No custom icon creation unless Lucide genuinely lacks coverage.

---

## Styling

Tailwind CSS. `class-variance-authority (cva)` for component variants. `clsx` for conditional classes.

**No hardcoded colors.** All colors go through semantic CSS-variable tokens:

```css
--color-bg-primary
--color-fg-primary
--color-accent
--color-success
--color-danger
--color-warning
--color-info
--color-category-1..N   /* one per category color slot */
```

shadcn/ui is CSS-variable-driven natively — this approach is compatible.

**v1 themes:** light, dark, system (auto-detect). Architecture is ready for additional themes.

---

## `formatAmount()` — The Money Display Function

Every component that displays a monetary amount goes through `formatAmount()`. The function chains:

1. **Locale format** — `Intl.NumberFormat` using the user's locale preference (`1,234.56` / `1.234,56` / `1 234,56` / `1'234.56`). Per-user setting, not household-level.
2. **Privacy mode** — if privacy mode is active, applies `full_blur` (→ `••••`) or `partial_blur` (→ `$•,•••`).
3. **Output** — returns formatted string.

The data layer stores raw `NUMERIC`. Formatting is purely display-layer. No formatting logic in backend responses.

---

## Charts (First-Class, In-App)

Built with **Recharts**. Eight named charts ship as polished, interactive, drill-downable components:

| # | Chart | Key features |
|---|-------|-------------|
| 1 | Net worth curve | Multi-account, multi-currency, goal/target overlays |
| 2 | Cash flow per period | Income vs. expenses with forward projection |
| 3 | Category breakdown | Spending by category, comparison to prior periods |
| 4 | Budget burn-down | Actual vs. planned within period, per line |
| 5 | Goal burn-up | Actual contribution vs. required pace, with projection |
| 6 | Debt payoff schedule | Per-account amortization, total interest visualization |
| 7 | Calendar heatmap | Spending intensity by day |
| 8 | Recurrence consistency | Amount/timing variance over time per tracked recurrence |

Long-tail analytical questions are exported to external tooling via `/api/v1/.../export` endpoints (CSV/JSON) and the Prometheus `/metrics` endpoint.

---

## Forms

React Hook Form + Zod. shadcn's `Form` component is built on this combination. Zod schemas define validation.

---

## Code Splitting

Heavy pages are lazy-loaded via `React.lazy` + `Suspense` to keep the initial bundle tight.

| Lazy page | Reason |
|-----------|--------|
| `ProjectionsPage` | Recharts-heavy, computation-heavy |
| `InsightsPage` | react-markdown + chart components |

Pattern in `router.tsx`:
```tsx
const ProjectionsPage = lazy(() =>
  import('@/pages/projections/ProjectionsPage').then((m) => ({ default: m.ProjectionsPage }))
)
// Wrap in <Suspense fallback={<PageSkeleton />}>
```

All other pages are statically imported.

---

## TanStack Query Caching Conventions

| Data | staleTime | gcTime | Notes |
|------|-----------|--------|-------|
| Transactions | `0` | default | Always fresh — new ingest can arrive any time |
| Balance history | `30_000` | default | Semi-stable; changes only on reconciliation |
| Projections | default | `5 * 60 * 1000` | Expensive to compute; keep in cache longer |
| Sessions | `0` | default | Security-sensitive; never serve stale |
| Everything else | `60_000` (orval default) | default | Standard 60s stale window |

**Hover prefetch:** `AccountCard` prefetches the account detail query on `mouseenter` with a 300ms debounce via `qc.prefetchQuery()`. This masks navigation latency without burning requests for quick cursor passes.

---

## PWA

`vite-plugin-pwa` from day one, generating manifest + service worker via Workbox.

Configured for:
- App shell caching
- API GET response caching (stale-while-revalidate)
- No precaching of authenticated content
- Opt-in install prompt

**Icons:** `apps/frontend/public/icon-192.png` and `icon-512.png` are required for the PWA manifest. Regenerate them if the brand color changes. Both are committed — do not add to `.gitignore`.

---

## E2E Tests (Playwright)

Test files live in `apps/frontend/e2e/`. Separate from Vitest — excluded from Vitest config and ESLint.

```
e2e/
  global-setup.ts        # registers test user, creates household, stores auth state
  fixtures.ts            # extends base test: storageState, credentials, apiPost helper
  auth.spec.ts
  accounts.spec.ts
  transactions.spec.ts
  budgets.spec.ts
  goals.spec.ts
  classification.spec.ts
```

**Scripts:**

| Script | What it does |
|--------|-------------|
| `pnpm e2e` | Headless Playwright run (chromium) |
| `pnpm e2e:headed` | Same, with browser visible |
| `pnpm e2e:report` | Open last HTML report |

**Isolation:** `global-setup.ts` creates a shared household once. Each test creates its own data — never shares state across tests.

**Config:** `playwright.config.ts` at `apps/frontend/`. Chromium only, 2 workers in CI, 1 worker locally when `CI` is not set.

---

## React Native Prep (v2/v3 Target)

What this means in practice today:

- All business logic in `domain/` — pure TypeScript.
- TanStack Query hooks are thin wrappers over domain modules.
- React components contain no business logic.
- Design tokens as CSS variables (portable to RN via token mapping).
- No DOM-specific code in anything outside React components.
