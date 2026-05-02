# Budgeting App — Decisions Ledger

**Purpose:** Single source of truth for every committed design decision from the planning phase. This is the document to verify against. The `DESIGN.md` (evaluator-facing) and `CLAUDE_CONTEXT.md` (build-facing) are derived from this ledger; if they disagree with this document, this document wins.

**How to use:** Read top-to-bottom. Each decision is tagged with the round it came from for traceability back to the conversation. Items marked `[NEEDS CONFIRMATION]` are decisions I'm not 100% sure we explicitly committed to — please confirm or correct before deriving the other docs.

**Format:** Decisions are grouped by round/topic. Each bullet is one committed decision in the form "X is Y" (with rationale only where rationale itself was decided, not just discussed).

---

## R0 — Foundational Context

- App purpose: personal/family financial budgeting and intelligence application.
- Initial deployment: dockerized, hosted on user's home lab.
- Frontend platform: PWA (web + mobile via PWA install).
- Native mobile apps: deferred to v2/v3, **React Native is the target path** for that phase. Architectural prep applies in v1.
- Account sync provider: **SimpleFIN** primary, with statement upload/auto-pull as supplementary ingestion paths.
- AI: **stretch goal**; app must function fully without it.
- User scope: family with user accounts, must degrade cleanly to single-user.
- Lifecycle posture: **hardened, long-lived application** (not a throwaway prototype).
- Banking jurisdiction assumed: US.

---

## R1A — Multi-User & Household Model

- Visibility model is selectable by the user at household creation, mutable later. Modes:
  - `fully_shared`
  - `separate_with_joint_view`
  - `role_based`
  - `admin_controlled`
- Account-level participation: every account has a `primary_holder` and an `authorized_users[]` list; this works regardless of household visibility mode (handles "I own the card, spouse is authorized" case).
- **Account grouping (`AccountGroup`)**: handles the case where a single underlying bank account (e.g., one credit card) appears as multiple feed entries (one per cardholder). The group represents the logical account; `primary_holder` and `authorized_users[]` live on the group. Transactions from any feed entry roll up to the single logical account for budgeting, net worth, and reporting — no double-counting balances. Detection heuristic: same institution + same balance + similar account name → candidate for grouping, surfaced to HITL.
- Role separation between **App Admin** and **household financial roles**:
  - `App Admin` — sysadmin role; manages OIDC config, integrations, encryption keys, backups, user invites; not necessarily a financial participant.
  - `Owner` / `Member` — financial roles within a household.
  - In a single-person deploy, App Admin and Owner collapse to one human wearing two hats.
- Authentication: **OIDC** (financial app, justified). External IdP handles authentication; app stores no passwords for OIDC-authenticated users.
- Auth implementation is **pluggable** (see R9 Decision 3). Local username/password is shipped as a reference plugin alongside OIDC for users without an external IdP.

---

## R1B — Account & Transaction Model

### Accounts

- **Manual / non-synced accounts** are first-class from day one (cash, vehicles, real estate, valuables, crypto wallets, etc.) for net worth tracking.
- Net worth tracking is a committed feature.

### Transactions

- Transaction lifecycle uses a **full state machine**: `pending → posted → reconciled`.
- **Splits are allocations, not children.** The transaction itself remains atomic (single row, single amount). Splits are a tagging/categorization layer over the transaction.
  - Sum of split allocations must equal the transaction amount.
  - An "uncategorized remainder" allocation is allowed for partial splitting.
  - Budgets and category reports aggregate over **split allocations**, not transactions directly.
  - A transaction with no splits gets an implicit single allocation to its assigned category.
- **Transfers** require explicit linkage:
  - User is asked whether a detected transfer is **internal** (links to an internal account) or **external** (links to nothing).
  - Detection is heuristic with manual override.
- **Refund pairing** is supported, mechanically similar to transfer pairing (same merchant, opposite sign, within N days, debit ≥ credit). Pairs net out cleanly in spending reports.

### Deduplication

- Dedup strategy is **layered**:
  1. Prefer source-provided ID (SimpleFIN ID, OFX `FITID`).
  2. Fall back to fuzzy match: `account + amount + date ± N days + normalized description`, with a confidence score.
  3. Below confidence threshold → manual merge queue (HITL).
- Source merge policy when same period from two sources: **SimpleFIN wins on the canonical record; statement is reference-only.** Confirmed.

### Currency & FX

- **Multi-currency from day one.** Every monetary column is paired with a currency column.
- Household has a `home_currency` for net worth rollups.
- FX strategy: **both** per-transaction snapshot AND daily rate table (Option 3).
  - Per-transaction snapshot: stores rate at transaction time on the transaction row → immutable historical truth ("how many USD did I spend that day?").
  - Daily rate table: enables current revaluation of foreign balances and goals.
- **Lazy currency population**: a daily rate row is only inserted when an account or transaction in that currency exists. No pre-population of all ISO currencies.
- Daily rates only; no intraday rates.
- For projections: foreign currencies project flat by default; configurable.

---

## R2A — Categories & Tags

- **Category hierarchy: 2 levels** (parent / child).
- Category tree is **household-scoped**.
- Default category tree is shipped as an **editable template** at household creation (seeded from the template into normal DB rows; users can edit, rename, or delete).
- **System categories** exist as immutable DB rows with `system: true, deletable: false, renameable: false`. Visible in the UI but locked. Initial system categories: `Transfer`, `Uncategorized`, `Income`, `Refund`.
- **Tags** are flat, many-to-many, household-scoped. Orthogonal to categories.
- "Who spent it" attribution lives on the **split allocation** via `attributed_to_user_id`, defaulting to the account's primary holder. Not encoded into category hierarchy.

---

## R2B — Rules Engine

- Shape: `IF (conditions) THEN (actions) WITH (priority)`.
- Conditions match on: `merchant_name`, `description`, `amount`, `account`, `direction (debit/credit)`, `transaction_type` (see income-source edge case).
- Operators: `equals`, `contains`, `starts_with`, `regex` (called "advanced pattern match" in UI), `amount_between`, `amount_equals`.
- Users can disable shipped/standard rules and define new ones.
- **Strictness setting** at household level governs ambiguity handling across multiple subsystems (rules, recurrence matching, dedup, transfer detection):
  - `strict` — multi-match → HITL queue, leave uncategorized. **DEFAULT.**
  - `best_guess` — highest priority wins, flagged for review.
  - `silent` — highest priority wins, no flag.
- Priority resolution: explicit integer priority, user-editable. Ties broken by rule creation date (older wins).
- **Manual recategorization sets `manually_categorized: true`** on the allocation; rule engine respects this and does not re-trigger.
- **Rule provenance** is recorded on every auto-categorized allocation (which rule fired, when).
- **Suggest vs. auto-apply** mode per rule. Suggest mode flags transactions for review without modifying them.
- ML-assisted categorization: **hooks left** but no implementation in v1. Architecture supports a "learn from manual categorizations" classifier as a future feature.
- Rules apply on transaction ingest. Re-running rules on history is a separate explicit user action.

---

## R2C — Recurring Detection

- **Both detected and declared recurrences** are supported.
- **Detected**: pattern-mined from history. Group by `(account, normalized_merchant, amount ± tolerance)`; require ≥3 occurrences with consistent intervals (weekly, biweekly, monthly, quarterly, annual ± few days). Output is a `RecurrenceCandidate` requiring user confirmation. **Never auto-promote**.
- **Declared**: user-defined, future-facing (new lease, new subscription, anticipated raise). May have no historical data.
- User can flag a single transaction as "start of new recurring series" to bootstrap a declared recurrence from one observation.
- Recurrence model fields:
  - `cadence`: `monthly`, `weekly`, `biweekly`, `semimonthly`, `annual`, `custom_cron`
  - `expected_amount` + `tolerance`
  - `expected_day_of_period`
  - `linked_category`, optional `linked_account`
  - `expected_amount_strategy`: `fixed`, `last_n_average`, `manual_estimate`, `external_signal`
  - `start_date`, optional `end_date`, `paused` state
- Variable-amount recurrences supported via `expected_amount_strategy`.
- **Missed/late detection**: if expected recurrence has not landed by expected date + tolerance, calendar shows "missed" indicator and projections still assume it's coming. Missed/late indicator **resets** on detected reconciliation (matching transaction arrives) OR manual dismissal. Dismissed alerts do not re-alert for the same instance.
- **Recurrence deviation alerts** (e.g., "Netflix went from $15.99 to $22.99 — price hike or plan change?") flow into the HITL queue.
- **Manual reconciliation override**: user can detach a transaction from its recurrence (e.g., "rent split externally this month") without breaking the series.
- **Multi-source split detection**: transactions originating from multiple internal accounts toward a single destination (e.g., rent paid half from checking A, half from checking B; or a purchase split across two cards) are flagged in the HITL queue. Two flavors:
  - *Split payment across cards*: same merchant + same day + amounts summing to a round-ish number or known expected amount → "possible split purchase across accounts."
  - *Split funding of a transfer*: two outbound transfers, same destination, same day → "possible multi-source transfer."
  - On confirmation, system creates a **payment group** linking the transactions. For reporting, the group is treated as a single logical spend event. Individual transactions retain their per-account attribution for reconciliation.
- Recurrences are **editable and archivable, never deleted**. `end_date` is mutable. Historical data unaffected by future edits.
- Transactions carry a `recurrence_id` reference for cheap historical lookups.

---

## R2 — Income Source Edge Case (Costco/Microsoft Problem)

- **`transaction_type` field** on every transaction, populated by a pre-rule classifier. Values: `payroll`, `refund`, `transfer`, `fee`, `interest`, `dividend`, `regular`.
- Classifier signals: ACH SEC code (when present), description tokens (`PAYROLL`, `DIR DEP`, `DIRDEP`, `DD`, `SALARY`, `WAGES`, `EARNINGS`), recurrence cadence/stability, OFX `NAME`/`PAYEEID` fields, amount magnitude vs. account history.
- **`IncomeSource` entity**, household-scoped, attributable to a user:
  - `employer_name`, `attributed_to_user_id`, `expected_cadence`, `expected_amount_range`, `account_id`
  - `variability_model`: `fixed`, `range (min/max)`, `historical_distribution`
- Models bonuses, RSU vests, expense reimbursements as **related but distinct entity types** under income source (e.g., `income-payroll`, `income-bonus`, `income-rsu`, `income-reimbursement`). Confirmed.
- **Classification pipeline order (deterministic):**
  1. Type detection
  2. Income source match (locks to `Income > Salary` or sub-category regardless of merchant rules)
  3. User rules (rules can opt into matching specific types via `transaction_type` condition)
  4. Fallback uncategorized
- Recurrence detector surfaces `IncomeSource` candidates during initial historical import: "We detected recurring credits from MICROSOFT — is this employment income? Whose?"
- **Income splits** for lump-sum paychecks: same allocation mechanism as transaction splits, applied to income, supports separable components (base + tips + overtime + commission).
- **Paycheck split deposit detection**: when a paycheck is split across multiple accounts via direct deposit (e.g., 80% to checking, 20% to savings), the system detects two deposits from the same employer on the same day across accounts owned by the same user and proposes linking them as a single income event.
  - `IncomeSource` gains a `deposit_split_pattern`: list of `{ account_id, amount_or_percentage }` entries.
  - Combined total counts as "income for the period" in budget calculations — no double-counting.
  - Surfaced in HITL on first detection: "We see two deposits from COSTCO totaling $X — is this a single paycheck split across accounts?"
  - Once confirmed, the pattern is remembered. Recurrence detector notices amount shifts (e.g., user adjusts direct deposit allocation) and flags them.

---

## R3A — Budgets

### Plan vs. Method separation

- A `Budget` is a time-bounded plan: which categories get how much, over what period. It is **method-agnostic**.
- A `BudgetMethod` is the policy that governs how the plan is constructed and enforced. Methods are composable as a **strategy pattern**, not an enum on the budget.

### Budget structure

- `Budget` fields: name, period, start date, optional end date, owning user or household, method.
- `period` values: `monthly`, `weekly`, `biweekly`, `semimonthly`, `annual`, `custom`.
- `BudgetLines`: one per category (or category + tag combination), with planned amount, currency, rollover policy.
- **Multiple concurrent budgets per household** are supported.
- **Budget scope**: `{ accounts: [], categories: [], tags: [] }` — all three supported, intersected, empty means "any."

### Rollover policies (per BudgetLine)

- `none` — unspent resets each period
- `accumulate` — unspent carries forward indefinitely (true envelope)
- `accumulate_capped` — carries forward up to a max
- `debt_carry` — overspending carries as negative into next period
- `reset_on_overspend` — overspending zeros next period's allocation

Different lines in the same budget can have different rollover policies.

### Methods

- `Zero-based`: constraint — sum of `BudgetLines` must equal `expected_income` for the period.
- `Envelope`: constraint + behavior — every spending category must have a line; spending against a depleted envelope triggers HITL or block.
- `50/30/20`: constraint over category metadata — categories tagged `needs`/`wants`/`savings`; budget enforces aggregate ratios.
- `Percentage-based`: lines defined as percentages of income, resolved to absolutes per period.
- `Rolling-average`: line amounts auto-set from last N periods' actual spending.
- `Manual`: no enforcement; planned amounts are advisory.
- `None`: no method applied. Budget exists as a pure tracking/observation tool — no planned amounts, no constraints, no enforcement. User sees what they spend without being told what they should spend. Distinct from `Manual` (which still has planned amounts, just unenforced). `None` means "don't budget this, just track it."

### Income strategies (`expected_income_strategy`)

- `fixed` — declared flat amount
- `from_income_sources` — sum of declared `IncomeSource` projections for the period
- `last_period_actual` — what actually came in last period
- `rolling_average` — average over last N periods (N user-configurable, default 3)
- `manual_per_period` — user enters at period start, no auto-calc

### Versioning

- Budgets are **versioned** via effective-dated rows (option chosen in R6).
- Edits create a new version with effective date; period resolves the budget version active on its start date.
- Editing a budget never rewrites historical periods.

---

## R3B — Debts

### Model

- `DebtAccount` is an annotation layer over a regular `Account` with `type ∈ {credit_card, loan, line_of_credit, ...}`.
- `DebtAccount` fields: `principal_balance`, `apr`, `minimum_payment_strategy` (`fixed_amount` | `percentage_of_balance` | `from_statement`), `statement_day`, `due_day`, `payoff_target_date` (optional).
- **Multi-balance debt accounts from day one**: `DebtAccount` is a parent of `DebtBalance` rows, each with its own APR, term, and optional promotional period (e.g., 0% balance transfer until X).
- **APR-with-history** on every debt balance. Rate changes are tracked as effective-dated rows.

### Plans

- `DebtPlan` is a strategy applied across a set of `DebtAccounts`.
- `DebtPlan` fields: method (`avalanche` | `snowball` | `custom` | `none`), monthly extra payment budget, snowball-flow setting (paid-off debt's minimum redirects to next; default true for both methods, separable).
- `custom` plans use user-defined priority order.
- `none` means debt accounts are tracked (balances, minimums, APRs) but no payoff strategy is active and no extra-payment recommendations are generated.

### Engine outputs

- Payoff schedule (per-account, per-month, principal/interest split).
- Total interest paid, time-to-debt-free, savings vs. minimums-only.
- Per-month payment recommendations.
- Reactive updates when actual payments deviate from plan.

### Plan-Budget linkage

- Debt engine produces **`Recommendation` objects**, never directly modifies budgets.
- Recommendations route through HITL queue (or auto-apply if user has flipped that switch per-source).

### Versioning

- **Debt plans are versioned** (same effective-dated pattern as budgets).
- Plan switches mid-stream preserve history (e.g., "you switched from snowball to avalanche on date X").

### History posture

- Default to history preservation. Reconciliation is explicit user action.

---

## R3C — Goals

### Goal types (modeled from day one)

- `savings_target` — accumulate $X by date Y in account(s) Z
- `purchase` — save $X for a specific named thing
- `debt_payoff` — view over the DebtPlan; appears in the goals list for unified UX
- `net_worth` — reach $X net worth by date Y
- `category_reduction` — reduce monthly spend in category Z to $X
- `emergency_fund` — accumulate N months of expenses (computed dynamically from recent budget actuals)
- `recurring_contribution` — contribute $X/month to account Y (a discipline goal)
- `minimum_balance` — maintain account balance above a threshold. No end date. Alerts when balance drops below minimum. Threshold editable at any time.

Goals are **0+**: a household can have zero, one, or many goals. No goal is required.

### Funding strategy

- `funding_strategy`: `dedicated_account` OR `virtual_allocation` — **both supported.**
- Virtual allocation tracks a slice of a larger balance via attributed contributions.
- **Funding sources** for a goal can include:
  - Specific accounts
  - Specific users' income streams (e.g., "both our paychecks contribute to the vacation fund")
  - A unified household stream ("any unallocated surplus from any account")
- Contribution tracking attributes contributions per user even for jointly-funded goals, enabling per-user progress reporting ("you contributed $X, spouse contributed $Y, total $Z toward $W target").

### Contribution patterns

- **All three supported**, layered:
  - Manual (user logs contribution)
  - Tag-driven (transactions tagged with goal count as contributions)
  - Recurring rule (e.g., "every paycheck, $200 → vacation fund"; implemented as a `RecurringTransfer` with a `goal_id`)

### Conflict resolution

- **Explicit per-period allocation** when goals compete for the same dollars.
- Priority ordering with auto-allocation can layer on later but is not v1.

### On-track calculation (burn-up)

Per goal, computed at each evaluation tick:
- `required_pace` — what contribution rate should be to hit target on time
- `actual_pace` — observed contribution rate over a trailing window
- `cumulative_actual` vs. `cumulative_expected` — the burn-up gap
- `projected_completion_date` — extrapolating actual_pace forward
- `gap_to_close` — dollars short
- `status`: `ahead | on_track | behind | at_risk | off_track` (configurable thresholds)

Default pace: linear. Override available for non-linear (lumpy savers).

### Over-target behavior

- Goals are stored as **uncapped accumulators**. `progress_pct` can exceed 100.
- Display layer decides whether to show "115% of target" or "complete + $X surplus" per user preference per goal.
- Completion is a **separate user action**, never automatic.

### Completion policy (per goal)

- `archive_on_complete`
- `prompt_on_complete` — surface to HITL: "Goal hit. Archive, extend target, or clone?" **DEFAULT.**
- `auto_extend` — increment target by configured amount, keep going (good for emergency funds)
- `auto_clone` — archive completed instance, start new instance with same parameters (good for annual goals)
- `convert_to_recurring` — completed goal becomes a recurring contribution discipline goal

---

## R3 — Recommendations (cross-cutting)

- **`Recommendation` is a first-class entity.**
- Subsystems communicate via recommendations, not direct writes (debt → budget, recurrence → income source, refund → transfer, goal → budget, AI → anything).
- Fields: `target` (subsystem + entity), `proposed_value`, `rationale` (human-readable + structured), `source` (which subsystem produced it), `confidence` (optional), `expires_at`.
- Routes through HITL queue by default.
- Per-source auto-apply switch available (user opts in to specific automation).
- Rationale field carries forward to audit log when accepted.

---

## R4A — Projections Engine

- **Single deterministic engine.** Reused by debt scheduling, goal burn-ups, budget income forecasts, calendar forward view, scenario analysis.
- Inputs: current account balances (snapshot at `as_of`), active recurrences, active budgets, active debt plans, active goals, FX rates (current + projected; foreign currencies project flat by default).
- Outputs:
  - Timeline of `ProjectedEvent` objects per account, dated, with `confidence` (high for fixed recurrences, lower for variable, lowest for budget-line-implied).
  - Aggregations: per-period cash flow, per-account balance curves, net worth curve.
  - Breach events: "checking goes negative on [date]," "credit card hits limit on [date]," "emergency fund target met on [date]."
- **Hard cap on projection horizon.** Default 12 months, configurable up to 60.
- **Scenario / what-if support from day one.** A scenario is a set of override deltas applied on top of base inputs. Scenarios are not persisted by default; user can save one as a named projection.
- **Variable amount handling**: `projection_strategy` per source — `p25 | p50 | p75 | last_n_average | manual_override`. Default `p50`. User-configurable per recurrence with household-level default.
- **Recompute trigger**: on-demand with caching keyed to (inputs hash, as_of date), invalidated on any input change. No pre-compute on ingest.

---

## R4B — Calendar

- Layers shown on the calendar:
  - Posted transactions (by category color)
  - Pending transactions (visually distinct)
  - Expected recurrences (confidence-graded; fixed = solid, variable = dashed/translucent)
  - Budget period boundaries (overlay)
  - Goal milestones
  - Debt due dates
  - HITL queue badges
- **Aggregation views**: day, week, month, **plus pay period**.
- **Pay period view** specifics:
  - Defined per `IncomeSource`: anchor date + cadence (`weekly`, `biweekly`, `semimonthly_1_15`, `semimonthly_15_eom`, `monthly`, `every_n_days`, `custom`).
  - For multi-earner households: user picks which income source's pay period drives the view, or selects "union of all" for visualization.
  - Budgets can opt into pay-period boundaries instead of calendar-month.
- Forward projection horizon matches projections engine (12 months default).
- Calendar renders only the visible window; lazy-loads on month navigation.
- **Click-through on a future event**: opens detail panel (source recurrence + projection confidence + ability to edit underlying recurrence or override this single instance).
- Single-instance overrides become a **`RecurrenceException` row** (one-off skip, one-off amount change, one-off date shift).

---

## R4C — AI Insights

### Provider abstraction

- `InsightProvider` interface, implementations:
  - `LocalOllama`
  - `LocalLlamaCpp`
  - `Anthropic`
  - `OpenAI`
  - `Disabled`
- `provider_priority` list per household; falls back gracefully if a provider is unavailable.
- AI is **additive**. App functions fully without any LLM. Even deterministic insights work without LLM. AI provider failure or absence degrades gracefully to "no insights surfaced."
- AI is **never on the critical path** of categorization, budgets, projections, debt plans, or goals.

### Insight categories (scoped)

- Anomaly detection
- Pattern surfacing
- Recommendation rationales (natural-language explanations)
- Question answering (parsed against actual data)
- Categorization assistance for un-rule-matched transactions (suggestion routed through HITL)
- Forecast narratives

### Architectural rules

- **LLM never touches the database directly.** Receives structured data via tool calls or RAG-style retrieval. Returns structured output. Application layer applies changes.
- **Insight outputs are `Recommendation` objects.** Routed through HITL like any other recommendation.
- **Audit trail on every LLM call**: provider, model, prompt template, prompt fingerprint (hash, not full prompt), response, tokens, cost, household.
- **Token/cost budget management**: per-household `ai_token_budget` and `ai_cost_budget` (monthly caps). Provider calls check remaining budget before executing. Overage behavior configurable: `block` (default), `warn_and_continue`, `silent`. Usage tracking per provider, per model, per insight category. Surfaced in a simple usage dashboard.

### Privacy levels (`ai_data_sharing`)

- `disabled` — no remote calls ever
- `generalizations_only` — only abstract patterns leave the box (no amounts, no merchants, no dates beyond period granularity). **DEFAULT for remote providers.**
- `aggregates_only` — category-level totals and aggregate stats; amounts allowed; merchant names redacted/hashed
- `redacted` — transaction-level data with PII fields stripped (account numbers, full descriptions, income source identities)
- `full` — everything; locally-running providers only; **hard-gated by provider type, not user preference**

The redaction layer is its own subsystem with explicit tests per level. Treated as security-critical code.

---

## R4D — Audit, History, Reversibility

### Audit log

- **Append-only** `AuditEvent` table. Append-only enforced via DB role permissions (app role has INSERT but not UPDATE/DELETE on this table).
- Fields:
  - `id` (UUIDv7)
  - `occurred_at` (TIMESTAMPTZ, UTC)
  - `actor_type`: `user | system | automation`
  - `actor_id` (UUID, nullable; `user_id` when actor_type = user)
  - `actor_source` (text; `'rule_engine'`, `'recurrence_detector'`, etc.)
  - `household_id` (FK)
  - `entity_type` (text)
  - `entity_id` (UUID)
  - `operation`: `create | update | delete | archive | merge | split | apply | accept | reject`
  - `delta` (JSONB; **JSON Patch RFC 6902** format)
  - `rationale` (text, nullable)
  - `source_event_id` (UUID, nullable; links reversals to originals)
- Indexes: `(household_id, occurred_at DESC)`, `(entity_type, entity_id, occurred_at DESC)`.

### Soft delete

- Every user-facing entity has `archived_at TIMESTAMPTZ NULL` and `archived_by UUID NULL`.
- Hard delete is admin-tool-only and rare (e.g., GDPR removal).

### Reversibility

- Every change written by an automated subsystem (rule engine, recurrence detection, refund pairing, transfer detection, AI suggestions) is **reversible by the user**.
- Reversal writes a new audit event referencing the original via `source_event_id`. History is appended, never mutated.

### Retention

- **Forever**, for personal-scale single-household app.

### Sourcing posture

- Traditional CRUD for read model + audit log alongside. **Not full event sourcing.**

---

## R4E — Security

### Encryption at rest

- **Application-layer encryption** for sensitive fields (not full-DB encryption):
  - Account numbers, routing numbers
  - Aggregator credentials (SimpleFIN tokens, OFX credentials)
  - OIDC tokens
  - AI provider API keys
- Aggregator credentials never logged, never sent to AI providers, encrypted at rest, rotatable.

### Master key custody

- **User-configurable** per deployment:
  - `env_var` (simplest, weakest)
  - `file` (file path + permissions checked at startup)
  - `vault` (pluggable backend: HashiCorp Vault, Infisical, sops/age, AWS Secrets Manager)
- App refuses to start if configured mode is not satisfiable.
- Re-key procedure (decrypt with old, re-encrypt with new) supports migration between modes.
- **Key rotation**: periodic re-encryption with a new master key supported, so a leaked old key doesn't compromise data encrypted after rotation.
- **Breach detection logging**: failed decryption attempts logged and alerted. If someone is trying keys against encrypted fields, the system surfaces it.
- **Documented threat model**: application-layer encryption protects against DB file theft. It does NOT protect against full host compromise where the attacker obtains both DB and master key. For that threat, use vault-mode key custody with separate secrets infrastructure.

### Authentication

- OIDC handles authentication; no passwords stored for OIDC users.
- Sessions: short-lived JWTs (15 min) + refresh tokens.
- Tokens stored as **httpOnly, Secure, SameSite=Strict** cookies. Not localStorage.
- Logout invalidates server-side.
- Rate limiting on auth-receive endpoint.
- **Idle timeout**: configurable idle timeout forces session invalidation. Default 30 minutes, App Admin configurable. Implemented as sliding window on JWT refresh mechanism — if no API activity within the window, refresh token is invalidated server-side, next request forces re-auth.

### Step-up auth

- App Admin actions (adding household member, changing encryption keys, exporting full data) require step-up auth (re-enter password, TOTP confirmation).
- Standard Owner financial actions remain session-authenticated.

### Read-only mode

- Panic switch that disables all writes (including aggregator sync) without taking the app down.

### Privacy viewing mode (Actual-style)

- Toggle on top-level UI, **persistent per device/session** (not per household).
- Replaces all monetary amounts with blur or `••••`.
- Applies to: balances, transaction amounts, budget figures, goals, debt balances, projections, calendar totals, charts (axes blurred, shapes preserved).
- Does **not** apply to: category names, merchant names, dates.
- **`partial_blur` mode** shows magnitude (`$•,•••`) without exact values.
- Implementation: render contract — every component displaying money goes through a `formatAmount()` call that respects active privacy mode.

### Backup

- Nightly logical Postgres dump.
- Encrypted with a separate backup key.
- Documented and CI-tested restore procedure (the procedure is a script, not a wiki page).
- Storage: local volume always; optional S3-compatible upload (see R9 Decision 5).

---

## R5 — Subsystem Boundaries & Module Structure

### Architecture style

- **Modular monolith.** Single FastAPI app, single Postgres, single worker pool, strict module boundaries enforced in code.

### Modules

- `accounts` — Account, DebtAccount, DebtBalance, ManualAccount entities; balance reconciliation; account lifecycle
- `transactions` — Transaction, SplitAllocation; dedup; transfer pairing; refund pairing
- `ingest` — SimpleFIN client, OFX/QFX parser, CSV import, statement upload, ingestion pipeline up to handing transactions to classification
- `classification` — categories, tags, rules engine, transaction-type detector, income source registry
- `recurrences` — declared and detected recurrences, deviation alerts, RecurrenceException
- `budgets` — Budget, BudgetLine, BudgetMethod implementations, period resolution, versioning
- `debts` — DebtPlan, payoff scheduling, strategy implementations
- `goals` — Goal entities, goal types, burn-up tracking, completion policies
- `projections` — single projection engine; consumed by budgets, debts, goals, calendar
- `recommendations` — Recommendation entity, HITL queue, routing, application
- `insights` — AI provider abstraction, redaction layer, prompt templates, response handling
- `audit` — AuditEvent log, change capture, replay tooling
- `households` — Household, User, membership, visibility modes, OIDC integration, App Admin separation
- `security` — encryption key management, secret storage abstraction, privacy mode state
- `platform` — shared utilities: money/Decimal handling, FX rate management, time abstractions, common types

### Inter-module communication

- **Synchronous interface calls** for read paths and same-transaction writes.
- **Domain events** for cross-cutting reactive logic. Subscribers don't know about each other.
- Events processed in-process for v1 (synchronous handlers within the same DB transaction where appropriate; async handlers via worker queue for heavier work).

### Boundary enforcement

- **`import-linter`** in CI enforces module-to-module import rules.
- Each module has `__init__.py` with explicit `__all__`.
- **No cross-module DB joins in queries.** Each module queries its own tables; cross-module data composed at service layer.
- **Per-module README** documenting ownership, public interface, emitted events, consumed events.

### Security principle

- **Use established, audited libraries for security-critical functionality.** Never roll custom auth, encryption, or token handling when a well-maintained library exists. Specifically: `passlib`/`argon2-cffi` for password hashing, `python-jose` or `authlib` for JWT, `cryptography` for encryption, `authlib` for OIDC client. Security code is never vibe-coded without expert review.

### Extensibility commitments

- **Public API parity**: API the frontend uses is the public API. No internal/external split. Versioned `/api/v1/`, OpenAPI-documented, published.
- **Programmatic access tokens**: personal access tokens (per-user) and service tokens (headless integrations). Scoped, revocable, audited. Separate from session cookies.
- **Webhook subsystem**: outbound delivery to user-configured URLs. Signed payloads, retry-with-backoff, dead-letter queue. Event schema parallels internal SSE events.
- **Plugin contract via `pluggy`**. Defined extension points:
  - aggregator providers
  - budget methods
  - debt strategies
  - insight providers
  - export formats
  - statement parsers
  - **auth providers** (first committed plugin contract — local auth and OIDC are reference implementations)

---

## R6 — Data Layer

### Database

- **Postgres 16+.** Hard requirement.

### Schema strategy

- **One schema (`public`) with table prefixes per module** (e.g., `accounts_account`, `transactions_transaction`, `audit_event`).
- **Soft delete columns** (`archived_at`, `archived_by`) on every user-facing entity. Default queries filter archived rows via SQLAlchemy event hooks or a `Live` mixin.
- **Versioning via effective-dated rows**: single table with `effective_from`, `effective_to`; current version is `effective_to IS NULL`. Used for budgets and debt plans (and any other entity needing version history).

### Money & currency

- **`NUMERIC(19, 4)`** for all monetary amounts. Pair every money column with a `currency CHAR(3)` column.
- **`decimal.Decimal` everywhere** in Python. No floats for money, ever. Pydantic validators reject floats at API boundaries.
- **Locale-specific decimal/thousands formatting** is a per-user preference (not household-level). Options: `1,234.56` (US/UK), `1.234,56` (EU/Latin America), `1 234,56` (French/Scandinavian), `1'234.56` (Swiss). Implemented via `Intl.NumberFormat` in the frontend's `formatAmount()` function (same function that handles privacy mode). No custom formatting code. Data layer stores raw `NUMERIC`; formatting is purely display-layer.

### Identity

- **UUIDv7 primary keys**, app-side generated via `uuid_utils` library. Time-ordered for index locality; no enumeration risk.

### Time

- **System-generated timestamps** (import time, audit events, modification times): `TIMESTAMPTZ`, stored UTC. App-layer converts for display. Never `TIMESTAMP WITHOUT TIME ZONE`.
- **Bank-reported dates** (`posted_date`, `pending_date`, `occurred_at`): **`DATE` columns**, not `TIMESTAMPTZ`. These are calendar dates as reported by the bank; no timezone conversion applies. If an OFX source provides a full datetime with timezone, the date component is extracted in the source's timezone and stored as `DATE` (no UTC conversion that could date-shift).
- **Validation**: `posted_date` cannot be more than 7 days in the future (catches garbage data from malformed feeds). No validation comparing bank-reported dates to system import timestamps — they answer different questions and are independent.

### Migrations

- **Alembic.** Every schema change is a migration. No `Base.metadata.create_all()` in production paths.
- Reversible where possible; documented when not.
- Each migration tested in CI against a populated test DB (apply forward, downgrade, re-upgrade).
- Auto-generation reviewed before commit.

### Audit table specifics

- Append-only enforced via DB role permissions: app's role has INSERT but not UPDATE/DELETE on `audit_event`.

---

## R7 — Background Jobs

### Worker stack

- **ARQ** for the worker queue (Redis-backed, async-native).

### Job categories

- **Scheduled recurring**: SimpleFIN polling, FX rate fetches (daily), recurrence detection sweep, goal/budget status recalc, backup, audit retention sweep.
- **Triggered async**: fired by domain events. Recurrence pattern updates, projection cache invalidation, AI insight generation, statement parsing, refund-pairing.
- **User-initiated long-running**: historical statement import, full re-categorization, scenario projection. Progress reported back via job status.

### Job design rules

- **Idempotent.** Every job safe to run twice. Upsert by source ID, check existence before creating.
- **Bounded.** Hard timeouts per job class.
- **Observable.** Structured start/finish/error events. Results stored 24h for debugging.
- **Decoupled from request handlers.** API endpoints enqueue and return immediately with a job ID. No work in request thread.

### Worker pools

- **Two pools**, separated by workload:
  - `worker-fast` — short jobs, high concurrency. Event handlers, projection cache invalidations, single-transaction processing.
  - `worker-slow` — long jobs, low concurrency. Statement parsing, historical imports, AI provider calls, recurrence detection sweeps.
- Both pools share the same Redis and codebase; difference is configuration.

---

## R8 — API Surface

### Style

- **REST with OpenAPI** (FastAPI auto-generated). No GraphQL, no tRPC.

### URL structure

- Resource-oriented, household-scoped at URL level:
  - `/api/v1/households/{household_id}/accounts`
  - `/api/v1/households/{household_id}/accounts/{account_id}/transactions`
  - `/api/v1/households/{household_id}/budgets`
  - `/api/v1/households/{household_id}/budgets/{budget_id}/lines`
  - `/api/v1/households/{household_id}/recommendations`
  - `/api/v1/households/{household_id}/calendar?start=...&end=...&view=pay_period`
  - `/api/v1/households/{household_id}/projections?horizon_months=12&scenario_id=...`
- `/api/v1/` prefix from day one.
- **URL privacy**: API URLs containing UUIDs are protected in transit by TLS (encrypted by HTTPS; interceptor sees only the hostname). UUIDs (v7) are not enumerable, so knowing one doesn't help guess another. Frontend SPA routes use friendlier client-side paths (e.g., `/accounts`, `/budget`) — API paths with UUIDs appear only in network requests, never in the browser URL bar.

### Authentication

- OIDC redirect → app receives token → validates → issues short-lived JWT (15 min) + refresh token.
- Cookies: `httpOnly`, `Secure`, `SameSite=Strict`. Not localStorage.

### Real-time updates

- **SSE (Server-Sent Events)**. Endpoint: `/api/v1/households/{household_id}/events`.
- Filtered server-side by household membership.
- Events include: `recommendation.created`, `transaction.ingested`, `sync.completed`, `recurrence.detected`, etc.

### Offline behavior

- **Read-only offline.** Service worker caches:
  - App shell (HTML/CSS/JS bundle)
  - Most recent API responses for: accounts, recent transactions, current budget, active goals, current recommendations
  - Static assets
- **No write queue.** Mutations attempted while offline get a clear error and "try again when connected" message.

### Multi-device sync

- Handled by SSE; no additional infrastructure.

### API conventions

- **Pagination**: cursor-based (`?cursor=...&limit=50`). Not offset. Frontend presents as either traditional paginated view (page 1, 2, 3 buttons) or **infinite scroll** — user preference, togglable per list (transaction lists, recommendation queue, any long list). Both use the same cursor-based API underneath.
- **Filtering**: structured query params; complex queries get dedicated endpoints.
- **Errors**: **RFC 9457 (Problem Details)**. Every error has `type`, `title`, `status`, `detail`, `instance`.
- **Idempotency keys**: optional `Idempotency-Key` header on mutation endpoints.
- **ETags / If-None-Match** for cacheable read endpoints.
- **Bulk operation endpoints** (e.g., `POST /transactions/bulk-categorize`).

---

## Language & Backend Stack

### Language

- **Python 3.12+.** Decision rationale: existing proficiency, ecosystem fit (SimpleFIN, OFX, AI SDKs), vibe-coding quality with Claude Code, performance is irrelevant at this scale.

### Stack (committed)

- **Runtime**: FastAPI, SQLAlchemy 2.0 async, Pydantic v2, Alembic, ARQ, Postgres 16+, Redis.
- **Quality**: pyright strict mode, ruff (lint + format).
- **Testing**: pytest, pytest-asyncio, hypothesis, testcontainers-python, polyfactory, time-machine, respx, pytest-cov.

### Discipline rules

- `decimal.Decimal` for all money. Never float.
- All schema changes via Alembic migrations.
- SQLAlchemy 2.0 typed `Mapped` style.
- Async by default for I/O.
- Workers as separate process (not in-request).
- Property-based tests for financial logic (Hypothesis).
- Golden-file tests for projection engine.
- Scenario tests (end-to-end through real DB and worker) for integration.

---

## R9 — Deployment Topology

### Decision 1 — Container composition: Option C

- Default `docker-compose.yml` ships everything: Postgres, Redis, app, worker-fast, worker-slow, reverse proxy, optional Ollama.
- BYO mode documented via env vars and compose profiles. Users with existing infra disable bundled services and point env vars at their own.

### Decision 2 — Reverse proxy: bundled Caddy with disable option

- Caddy bundled by default. Listens on `:443`, auto-HTTPS via Let's Encrypt or local CA, terminates TLS, forwards plain HTTP to the app on internal Docker network.
- Disable via compose profile (e.g., `COMPOSE_PROFILES` excluding `bundled-proxy`). When disabled, app exposes plain HTTP port directly; user's external proxy terminates TLS and routes.
- **No double-proxy ever.** Either Caddy is the terminator or the user's external proxy is.
- Documentation includes per-proxy config snippets for nginx, Traefik, Caddy, and explicitly calls out SSE config requirements (e.g., `proxy_buffering off` for nginx).

### Decision 3 — OIDC / auth topology: Option C

- **Auth pluggable from day one** via `pluggy`.
- Reference implementations shipped: local auth (username + password + TOTP) and OIDC.
- Auth is the **first committed plugin contract**.

### Decision 4 — Secrets at runtime: Option B

- **Bootstrap secrets via env vars**: master key (per the user-configurable custody mechanism) + DB connection string.
- **Runtime secrets stored encrypted in DB**: SimpleFIN tokens, OIDC client secrets, AI provider API keys, OFX credentials. Decrypted only at use time.

### Decision 5 — Backup destinations: Option C

- **Local volume always.** Configured path inside container's volume.
- **Optional S3-compatible upload** when configured: any S3-compatible target (MinIO, B2, S3, R2, Wasabi).
- Env vars: `BACKUP_S3_ENDPOINT`, `BACKUP_S3_BUCKET`, `BACKUP_S3_ACCESS_KEY`, `BACKUP_S3_SECRET_KEY`, `BACKUP_ENCRYPTION_KEY`.
- Restoration tool ships with the app distribution (e.g., `python -m app.backup restore <file>`).
- Restore procedure tested in CI against a known-good snapshot.

### Decision 6 — Observability: Option B

- **Structured JSON logs to stdout** via `structlog`.
- **Prometheus `/metrics`** endpoint always on.
- **OpenTelemetry traces** opt-in via `OTEL_EXPORTER_OTLP_ENDPOINT` env var.
- Grafana not bundled; user brings their own or runs separate compose.

---

## R10 — Frontend

### Decision 1 — Framework: React

### Decision 2 — Build/meta-framework: Vite + React (SPA)

- No SSR. App is a pure SPA, served as static assets.

### Decision 3 — Language: TypeScript strict

- `tsconfig` strict mode.
- `noUncheckedIndexedAccess: true`.
- `noImplicitAny: true`.

### Decision 4 — State management: TanStack Query + Zustand

- **TanStack Query** for server state (cache, refetch, mutate, optimistic update).
- **Zustand** for cross-cutting client state.
- SSE events trigger TanStack Query cache invalidations.

### Decision 5 — API client: orval (OpenAPI-generated)

- Generates typed TypeScript clients **and** TanStack Query hooks from the FastAPI OpenAPI spec.
- Backend-frontend type sync enforced in CI (drift check fails the build).

### Decision 6 — Styling: Tailwind

- Tailwind CSS as the styling system.
- `class-variance-authority (cva)` for variants.
- `clsx` for conditional classes.

### Decision 7 — Component library: shadcn/ui

- Foundation. Owned source, copy-paste from CLI.
- Mantine's calendar component (`@mantine/dates`) as a specific exception if shadcn's calendar is insufficient for full month/agenda views.
- **Iconography**: source from established open-source icon libraries. Primary: **Lucide** (via `lucide-react`, already in the React ecosystem). Animated variants from lucide-animated.com where appropriate. No custom icon creation unless the library genuinely lacks coverage.

### Decision 8 — Charts & visualizations

- **First-class in-app charts** using Recharts. Eight named charts ship as polished, interactive, drill-downable components:
  1. Net worth curve (multi-account, multi-currency, with goal/target overlays)
  2. Cash flow per period (income vs. expenses, with forward projection)
  3. Category breakdown (spending by category, with comparison to prior periods)
  4. Budget burn-down (actual vs. planned within period, per line)
  5. Goal burn-up (actual contribution vs. required pace, with projection)
  6. Debt payoff schedule (per-account amortization, total interest visualization)
  7. Calendar heatmap (spending intensity by day)
  8. Recurrence consistency (variance over time per tracked recurrence)
- **Long-tail analytical questions** are exported to Grafana-class tooling via:
  - `/api/v1/.../export` endpoints returning CSV/JSON for any data slice
  - The Prometheus `/metrics` endpoint (already in R9 D6)
  - **Future** documented Postgres read-replica connection pattern (not implemented v1)
- **User-defined custom visualizations**: deferred to v2+. Mechanism TBD (saved chart configurations, custom dashboard layouts, or lightweight query builder over exported data).

### Decision 9 — Forms: React Hook Form + Zod

- shadcn `Form` is built on this combo.
- Zod schemas for validation.

### Decision 10 — PWA: vite-plugin-pwa from day one

- Generates manifest + service worker via Workbox.
- Configured for: app shell caching, API GET response caching with stale-while-revalidate, no precaching of authenticated content.
- Install prompt opt-in.

### Decision 11 — Theming

- v1: light + dark + system (auto-detect).
- Architecture: **semantic CSS-variable tokens** (`--color-bg-primary`, `--color-fg-primary`, `--color-accent`, `--color-success`, `--color-danger`, `--color-warning`, `--color-info`, `--color-category-1..N`, etc.).
- shadcn components are CSS-variable-driven; matches this approach natively.
- **Terminal-theme picker deferred** with prep:
  - v1.x: theme picker UI + 3-5 curated terminal-inspired themes shipped.
  - v2: user-uploadable theme JSON + theme validator (WCAG contrast checks, category color generator).
- Discipline now: no hardcoded colors; everything goes through semantic tokens.

### Native app prep (React Native as v2/v3 target)

- **Business logic in `domain/` modules**: pure TypeScript, no React, no DOM.
- **TanStack Query hooks** call into domain modules.
- **React components** are mostly rendering + event wiring.
- **Design tokens via CSS variables**, portable to RN through token mapping.
- **No business logic in components.** This is the load-bearing rule for keeping RN viable.
- Estimated UI code reuse with React Native: 0%. Estimated logic/hooks/types reuse: 50–70%.

---

## R11 — Development Workflow

### Decision 1 — Repository: monorepo

- Single git repo.
- Layout: `apps/backend/`, `apps/frontend/`, `packages/` for shared specs (OpenAPI definitions, fixtures).
- `pnpm workspaces` for the frontend; backend lives in its directory. No Nx/Turborepo at this scale.

### Decision 2 — Branching: trunk-based

- Main is always deployable.
- Short-lived feature branches.
- **Every change is a PR**, reviewed before merging to main (Claude Code output reviewed by user).

### Decision 3 — CI/CD: GitHub Actions hybrid

- **GitHub Actions hosted runners** for fast jobs (lint, type check, unit tests, frontend build).
- **Self-hosted runner on homelab** for slow jobs (testcontainers integration tests, Docker image build, deployment).

### Decision 4 — CI pipeline contents

**Backend (every PR):**
- `ruff check`
- `ruff format --check`
- `pyright --strict`
- `pytest` (unit, fast)
- `pytest -m integration` (testcontainers)
- Alembic migration test (forward, downgrade, re-upgrade against populated DB)
- `import-linter`
- Coverage threshold check (per-module thresholds, see Testing Strategy)

**Frontend (every PR):**
- `eslint`
- `prettier --check`
- `tsc --noEmit` (strict)
- `vitest`
- `vite build` succeeds
- Bundle size check (regression alert)

**Cross-cutting (every PR):**
- OpenAPI spec generation → orval client regeneration → diff check (fails if frontend client out of sync with backend API)
- Docker image build (when infrastructure changes)
- Dependency security scan (`pip-audit`, `npm audit`, `trivy`)

**Deployment (on merge to main, optional/manual):**
- Build Docker images, tag, push to **ghcr.io** (see Registry below)
- Update homelab via watchtower or manual `docker compose pull && up`

### Decision 5 — Pre-commit hooks: `pre-commit` framework

- ruff check + format
- prettier on changed files
- No merge conflict markers
- No large files
- Secret detection (`detect-secrets` or `gitleaks`)
- Type checking and tests stay in CI (too slow for hooks).

### Decision 6 — Testing strategy (committed coverage targets)

- **Financial logic modules** (`projections`, `budgets`, `debts`, `goals`, `transactions`, `classification`, `recurrences`, `platform/money`, `platform/fx`): **90%+ line coverage**, with property-based tests (Hypothesis) on every public function.
- **Audit, security, recommendations**: **85%+ line coverage**. Property tests on core invariants (audit log append-only, encryption round-trip).
- **API routes, ingestion adapters, CLI tooling**: **70%+ line coverage**.
- **Workers, schedulers, plugin loaders**: **60%+ line coverage**.
- **Frontend domain modules** (pure TS): **90%+ coverage** via vitest.
- **Frontend components**: smoke tests + critical-path component tests. No 100% chase.
- **End-to-end (Playwright)**: handful of critical flows (login → ingest → categorize → budget → recommendation accept). Run nightly + on release branches, not every PR.

**Test types committed:**
- Unit tests (pure logic)
- Property tests (Hypothesis) for financial invariants, dedup, recurrence, FX round-trip
- Integration tests (testcontainers Postgres + Redis)
- Golden-file tests for projection, debt amortization, budget period resolution
- Scenario tests (end-to-end through real DB and worker)
- Migration tests (forward + back against populated data)
- Contract tests (OpenAPI spec ↔ generated frontend client)

### Decision 7 — Documentation

- **In-repo:**
  - `README.md` (intro, quickstart, deeper-doc links)
  - `docs/` directory: architecture overview, design decisions, deployment guide, plugin development guide, API reference (auto-generated from OpenAPI)
  - Per-module `README.md`
  - `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `LICENSE`
- **Generated:**
  - API reference from OpenAPI → published static site (Redocly, Stoplight, or ReDoc)
  - TypeScript domain modules → TypeDoc
  - Python modules → docstring rendering (Sphinx or equivalent)
- **Design doc location:** lives in `docs/design/` as the foundation document. Subsequent decisions captured as **ADRs** (numbered, dated, standard format: context / decision / consequences).
- **Docs site**: Docusaurus, Mintlify, or Mkdocs Material generating from `docs/` markdown. [NEEDS CONFIRMATION — we agreed on shipping a docs site, but didn't lock which generator. Picking one is a deferred decision.]
- Documentation effort is part of every feature, not a separate phase.

### Decision 8 — Versioning & releases: SemVer with strict criteria

- **MAJOR (`X.0.0`)**: breaking change to public REST API contract, plugin contract, database schema requiring manual upgrade intervention (no auto-migration possible), or data export format.
- **MINOR (`0.X.0`)**: new feature, new module, new endpoint, new plugin extension point, additive schema change (auto-migrated), new currency/aggregator/AI provider support.
- **PATCH (`0.0.X`)**: bug fix, security fix, performance improvement, internal refactor with no observable change, doc-only change.
- **Pre-1.0 caveat**: while in `0.x`, MINOR bumps may include breaking changes (clearly called out in changelog with migration notes). 1.0 is the commitment line for backward compatibility on the public API.
- **Conventional Commits enforced** in commit messages (`feat:`, `fix:`, `chore:`, `docs:`, `breaking:`).
- **Release process**: tag → CI builds → Docker images pushed → GitHub Release with auto-generated changelog → docs site updated.

### Container Registry

- **GitHub Container Registry (ghcr.io).**
- Two tags per release: immutable version tag (`ghcr.io/<user>/<app>:0.1.0`) + moving `latest`.
- **Private until first release; public after** (under chosen LICENSE).
- GitHub Actions integration via `GITHUB_TOKEN`.

---

## Cross-Cutting / Architecture Principles (composed from all rounds)

These are not single-round decisions; they are principles that emerged from many decisions and govern the codebase.

- **Boring defaults that are well-defended.** Every "we picked X" has a reason; X is rarely the cleverest choice, often the most maintainable one.
- **Determinism is the core; AI is decoration.** Every core function works without LLMs. AI never on critical path.
- **Recommendations, not commands.** Subsystems suggest; user (or explicit auto-apply switch) decides. HITL queue is the single inbox.
- **Append, never mutate, history.** Audit log + soft delete + reversibility events.
- **Strict ordering in classification pipeline.** Type detection → income source → user rules → fallback. No silent magic.
- **Public API is the only API.** Frontend uses what plugins use what scripts use.
- **Modular monolith with enforced boundaries.** Modules can become services later; today's boundaries are tomorrow's seams.
- **Privacy-first defaults on AI.** `generalizations_only` for remote; `full` only for local; redaction layer is security-critical.
- **Money is `Decimal`. Currency is always paired.** Non-negotiable typing rules.
- **Bank dates are `DATE`; system timestamps are `TIMESTAMPTZ` (UTC).** Bank-reported dates and system-generated timestamps are independent, never compared, and stored in different column types.
- **Hardened means tested.** Property tests on financial logic; golden files on projections; scenario tests on integration.
- **Don't reinvent the wheel on security.** Use established, audited libraries for auth, encryption, token handling. Never vibe-code security-critical components without expert review.

---

## Items Marked `[NEEDS CONFIRMATION]`

These are points where I'm not certain we explicitly committed, vs. where I may be filling in plausible detail. Please review and confirm or correct:

1. **R11 D7 docs site generator** — we agreed to ship a docs site; we did not lock which generator. Decision deferred to implementation phase.

---

## Items Explicitly Deferred (not in v1)

- **Per-user category trees** (R2A) — household-scoped tree for v1; per-user layering can come later.
- **Multi-balance debt account UI polish** — modeled in schema from day one, but UI may ship simplified initially.
- **Promotional balances** — modeled, may not have full UI in v1.
- **Goal priority ordering with auto-allocation** — explicit per-period only in v1.
- **ML-assisted categorization** — hooks left, no implementation.
- **External-signal recurrence amount strategy** — modeled, may not have all data sources wired.
- **Terminal-theme picker** — architecture in v1, picker UI in v1.x, user-uploadable JSON in v2.
- **React Native build** — v2/v3.
- **Postgres read-replica for Grafana** — pattern documented, not implemented in v1.
- **Documented federated/multi-tenant deployment** — single-household focus for v1.
- **Webhook subsystem** — committed in design; can ship in v1.x without blocking v1 release. [NEEDS CONFIRMATION on timing — design committed, ship-in-v1-or-v1.x not specified.]
- **User-defined custom visualizations** — v2+. Mechanism TBD (saved chart configs, custom dashboards, or lightweight query builder).

---

*End of decisions ledger. Once verified, `DESIGN.md` (evaluator-facing) and `CLAUDE_CONTEXT.md` (build-facing) will be derived from this document.*
