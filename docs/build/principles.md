# Principles & Deferred Items

> Source: `DECISIONS.md` — Cross-Cutting / Architecture Principles, Items Explicitly Deferred

---

## Cross-Cutting Principles

These govern the entire codebase. When in doubt, default to these.

1. **Determinism is core; AI is decoration.** Every core feature works without any LLM. AI is never on the critical path of categorization, budgets, projections, debt plans, goals, or any user-facing workflow.

2. **Recommendations, not commands.** Subsystems suggest; the user (or an explicit opt-in auto-apply switch) decides. The HITL queue is the single inbox for all pending decisions. No subsystem writes directly into another subsystem's tables.

3. **Append, never mutate, history.** Audit log is append-only. Soft delete everywhere. Reversals write new events. History is never rewritten.

4. **Strict classification pipeline order.** Type detection → IncomeSource match → user rules → fallback. This order is deterministic and non-negotiable. No step skips or re-runs a prior step.

5. **Public API is the only API.** The API the frontend uses is what plugins use, what scripts use, what external integrations use. No internal/external split.

6. **Modular monolith with enforced boundaries.** `import-linter` in CI. Modules can become services later; today's boundaries are tomorrow's seams.

7. **Privacy-first AI defaults.** `generalizations_only` for all remote providers by default. `full` is hard-gated to local providers only — not a user preference that can be set for a remote provider.

8. **Money is `Decimal`. Currency is always paired.** Non-negotiable. No floats for money, anywhere, ever. Every money column has a currency sibling.

9. **Bank dates are `DATE`; system timestamps are `TIMESTAMPTZ` (UTC).** These answer different questions. They are independent, stored in different column types, and never compared to each other.

10. **Hardened means tested.** Property tests (Hypothesis) on all financial logic. Golden files on projections. Scenario tests on integration. Coverage targets are enforced in CI.

11. **Don't reinvent the wheel on security.** Use established, audited libraries for auth, encryption, and token handling. Never vibe-code security-critical components without expert review.

12. **Boring defaults, well-defended.** Every "we picked X" has a reason. X is rarely the cleverest choice — it is usually the most maintainable one.

---

## NOT in v1 (Explicitly Deferred)

These are decided/designed but not shipped in v1. Do not implement them unless the scope is explicitly expanded.

| Item | Notes |
|------|-------|
| Per-user category trees | Household-scoped tree only in v1; per-user layering is a future addition |
| ML-assisted categorization | Hooks left in the architecture; no implementation |
| Multi-balance debt account UI polish | Modeled correctly in the schema from day one; UI may ship in a simplified form initially |
| Promotional balances (debt) | Modeled in schema; may not have full UI in v1 |
| External-signal recurrence amount strategy | `external_signal` is a valid enum value in the recurrence model; data sources may not all be wired in v1 |
| Terminal-theme picker | Architecture and semantic token system are in v1; picker UI ships in v1.x; user-uploadable theme JSON in v2 |
| React Native build | v2/v3 target; code is structured for it but not built |
| Postgres read-replica for Grafana | Pattern documented; not implemented |
| Multi-tenant / federated deployment | Single-household focus for v1 |
| User-defined custom visualizations | v2+; mechanism TBD |
| Webhook subsystem | Design committed; ship timing v1 or v1.x (not a v1 blocker) |
| Goal priority ordering with auto-allocation | Explicit per-period allocation only in v1 |
