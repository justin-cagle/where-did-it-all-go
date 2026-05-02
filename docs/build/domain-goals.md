# Domain — Goals

> Source: `DECISIONS.md` — R3C (Goals)

---

## Goal Types (All Modeled in v1)

| Type | Description |
|------|-------------|
| `savings_target` | Accumulate $X by date Y in account(s) Z |
| `purchase` | Save $X for a specific named item |
| `debt_payoff` | View over the DebtPlan; appears in goals list for unified UX |
| `net_worth` | Reach $X net worth by date Y |
| `category_reduction` | Reduce monthly spend in category Z to $X |
| `emergency_fund` | Accumulate N months of expenses (N months computed dynamically from recent budget actuals) |
| `recurring_contribution` | Contribute $X/month to account Y — a discipline/habit goal |
| `minimum_balance` | Maintain an account balance above a threshold. No end date. Alerts when balance drops below threshold. Threshold is editable at any time. |

Goals are 0+: a household can have zero, one, or many. No goal is required.

---

## Funding Strategy

Two strategies supported; the user selects per goal:

**`dedicated_account`** — a specific account is the vessel for this goal. Contributions are actual deposits into that account.

**`virtual_allocation`** — tracks a slice of a larger balance via attributed contributions. No dedicated account required.

---

## Funding Sources

A goal's funding sources can include:

- Specific accounts
- Specific users' income streams (e.g., "both our paychecks contribute to the vacation fund")
- A unified household stream ("any unallocated surplus from any account")

For jointly-funded goals, per-user contribution tracking is maintained even with a shared funding source. This enables reporting like: "You contributed $800, spouse contributed $600, total $1,400 toward $3,000 target."

---

## Contribution Patterns

All three are supported and can be layered on the same goal:

| Pattern | Mechanism |
|---------|-----------|
| Manual | User logs a contribution explicitly |
| Tag-driven | Transactions tagged with the goal's tag count as contributions |
| Recurring rule | A `RecurringTransfer` with a `goal_id` automatically counts periodic contributions |

---

## Conflict Resolution

When goals compete for the same dollars, explicit per-period allocation is used. Each period, the user assigns dollars to goals. (Auto-allocation with priority ordering is deferred to a future version.)

---

## Burn-Up Tracking

Computed per goal at each evaluation tick:

| Field | Description |
|-------|-------------|
| `required_pace` | Contribution rate needed to hit the target on time |
| `actual_pace` | Observed contribution rate over a trailing window |
| `cumulative_actual` | Total contributed so far |
| `cumulative_expected` | What should have been contributed by now at required pace |
| `projected_completion_date` | Extrapolating actual_pace forward |
| `gap_to_close` | Dollars short of cumulative_expected |
| `status` | `ahead \| on_track \| behind \| at_risk \| off_track` (thresholds configurable) |

Default pace: linear. Override available for non-linear (lumpy) saving patterns.

---

## Over-Target Behavior

Goals are stored as uncapped accumulators. `progress_pct` can exceed 100 — the system does not stop tracking or cap contributions.

The display layer decides whether to show "115% of target" or "complete + $X surplus" — configurable per goal by the user.

Completion is a **separate user action**, never automatic.

---

## Completion Policy (Per Goal)

| Policy | Behavior |
|--------|----------|
| `archive_on_complete` | Automatically archives the goal when target is hit |
| `prompt_on_complete` | Surfaces to HITL: "Goal hit. Archive, extend target, or clone?" **DEFAULT.** |
| `auto_extend` | Increments target by a configured amount and continues (good for emergency funds) |
| `auto_clone` | Archives the completed instance and starts a new instance with the same parameters (good for annual goals) |
| `convert_to_recurring` | Completed goal becomes a recurring contribution discipline goal |
