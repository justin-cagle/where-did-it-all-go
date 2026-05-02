# Domain — Budgets

> Source: `DECISIONS.md` — R3A (Budgets)

---

## Plan vs. Method Separation

A `Budget` is a time-bounded plan: which categories get how much, over what period. It is **method-agnostic** — the same budget entity works with any method.

A `BudgetMethod` is the policy that governs how the plan is constructed and enforced. Methods are composable as a strategy pattern, not a hardcoded enum on the budget.

---

## Budget Fields

| Field | Values / Notes |
|-------|---------------|
| `name` | User-defined |
| `period` | `monthly \| weekly \| biweekly \| semimonthly \| annual \| custom` |
| `start_date` | When this budget begins |
| `end_date` | Optional |
| `owner` | User or household |
| `method` | Which BudgetMethod applies |
| `scope` | `{ accounts: [], categories: [], tags: [] }` — empty list = "any" |

**Multiple concurrent budgets per household are supported.** A household might have a joint household budget and individual personal budgets running simultaneously.

**Budgets can opt into pay-period boundaries** instead of calendar-month, driven by a linked `IncomeSource` cadence.

---

## BudgetLines

One line per category (or category + tag combination).

| Field | Notes |
|-------|-------|
| `category_id` | The category this line covers |
| `tag_id` | Optional — narrows the line to a category+tag intersection |
| `planned_amount` | Decimal amount for the period |
| `currency` | Paired with planned_amount |
| `rollover_policy` | See below |

---

## Rollover Policies (Per Line)

Different lines in the same budget can have different rollover policies.

| Policy | Behavior |
|--------|----------|
| `none` | Unspent resets to zero each period |
| `accumulate` | Unspent carries forward indefinitely (true envelope behavior) |
| `accumulate_capped` | Carries forward up to a configured maximum |
| `debt_carry` | Overspending carries as a negative into the next period |
| `reset_on_overspend` | Overspending zeros the next period's allocation |

---

## Budget Methods

| Method | Description |
|--------|-------------|
| `zero_based` | Sum of BudgetLines must equal `expected_income` for the period |
| `envelope` | Every spending category must have a line; spending against a depleted envelope triggers HITL or blocks |
| `50_30_20` | Categories are tagged `needs / wants / savings`; budget enforces aggregate ratios |
| `percentage_based` | Lines defined as percentages of income; resolved to absolute amounts per period |
| `rolling_average` | Line amounts auto-set from last N periods' actual spending |
| `manual` | No enforcement; planned amounts are advisory only |
| `none` | **Pure tracking mode.** No planned amounts, no constraints, no enforcement. User sees what they spend without being told what they should spend. Distinct from `manual` — `none` means "don't budget this category, just track it." |

---

## Income Strategies (`expected_income_strategy`)

| Strategy | Behavior |
|----------|----------|
| `fixed` | Declared flat amount per period |
| `from_income_sources` | Sum of declared IncomeSource projections for the period |
| `last_period_actual` | What actually came in last period |
| `rolling_average` | Average over last N periods (N user-configurable, default 3) |
| `manual_per_period` | User enters the amount at the start of each period; no auto-calc |

---

## Versioning

Budgets are versioned via effective-dated rows (see [data-layer.md](data-layer.md) — Versioning).

Edits create a new version with an effective date. Each budget period resolves the version active on its start date. Editing a budget **never rewrites historical periods.**

---

## Scope

Budget scope filters which transactions count against the budget:

```json
{
  "accounts": ["uuid-1", "uuid-2"],
  "categories": ["uuid-3"],
  "tags": ["uuid-4"]
}
```

Empty list on any field means "any" (no restriction on that dimension). All three dimensions are intersected.
