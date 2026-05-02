# Domain — Projections Engine

> Source: `DECISIONS.md` — R4A (Projections Engine)

---

## Single Deterministic Engine

One projection engine, reused by all consumers:

- Debt scheduling (amortization)
- Goal burn-up tracking
- Budget income forecasts
- Calendar forward view
- Scenario / what-if analysis

All consumers call the same engine with the same interface. No separate "debt projector" or "goal projector."

---

## Inputs

| Input | Notes |
|-------|-------|
| Current account balances | Snapshot at `as_of` date |
| Active recurrences | With expected amounts and cadences |
| Active budgets | Period definitions and line amounts |
| Active debt plans | Amortization parameters |
| Active goals | Targets, funding sources, contribution rates |
| FX rates | Current daily rates + projection assumption (flat by default for foreign currencies; configurable) |

**Foreign currency projection default:** foreign-currency balances and recurrences project flat (no rate movement assumed). Configurable per recurrence.

---

## Outputs

**`ProjectedEvent` timeline** — one event per projected cash flow, per account, with a `confidence` value:

- `high` — fixed recurrences with exact amounts
- `medium` — variable recurrences (amount estimated from strategy)
- `low` — budget-line-implied spend (most uncertain)

**Aggregations:**
- Per-period cash flow (income vs. expenses)
- Per-account balance curve over time
- Net worth curve over time

**Breach events** — the engine identifies and surfaces:
- "Checking goes negative on [date]"
- "Credit card hits limit on [date]"
- "Emergency fund target met on [date]"

---

## Horizon

Default: **12 months**. User-configurable up to **60 months**.

---

## Variable Amount Handling

Each recurrence has a `projection_strategy`:

| Strategy | Description |
|----------|-------------|
| `p25` | 25th percentile of historical amounts |
| `p50` | Median of historical amounts. **DEFAULT.** |
| `p75` | 75th percentile |
| `last_n_average` | Average of the last N occurrences |
| `manual_override` | User-declared fixed amount for projection purposes |

Household-level default is `p50`. User can override per recurrence.

---

## Scenarios / What-If

Scenario support is built in from day one. A scenario is a set of override deltas applied on top of the base projection inputs:

- Add or remove a recurrence
- Change an income amount
- Modify a debt plan's extra payment
- Adjust a goal's contribution rate

Scenarios are **not persisted by default** — they are transient what-if sessions. Users can save one as a named projection if they want to retain it.

---

## Caching & Recompute

Projections are computed **on-demand**, not pre-computed on ingest.

Cache key: `(inputs_hash, as_of_date)`. The inputs hash covers all active recurrences, budgets, debt plans, goals, and FX rates.

Cache is **invalidated on any input change** — a new recurrence, a budget edit, a debt payment reconciliation, etc.

No background pre-computation in v1.
