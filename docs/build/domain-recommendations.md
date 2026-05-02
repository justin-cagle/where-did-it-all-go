# Domain — Recommendations

> Source: `DECISIONS.md` — R3 (Recommendations cross-cutting)

---

## First-Class Entity

`Recommendation` is a first-class domain entity, not a UI concept. It is the communication mechanism between subsystems. Subsystems suggest; users (or explicit auto-apply switches) decide.

**No subsystem writes directly into another subsystem's tables.** All cross-subsystem mutations go through the Recommendation → HITL → application pipeline.

---

## Recommendation Fields

| Field | Type / Notes |
|-------|-------------|
| `target` | Subsystem + entity reference (e.g., `budgets:budget_id:line_id`) |
| `proposed_value` | Structured data describing the proposed change |
| `rationale` | Human-readable explanation + structured metadata |
| `source` | Which subsystem produced it |
| `confidence` | Optional float — subsystem's confidence in the recommendation |
| `expires_at` | Optional — recommendations can be time-limited |

---

## HITL Queue

All recommendations route to the HITL (Human-In-The-Loop) queue by default. The queue is the single inbox for all pending decisions.

**Per-source auto-apply switch:** users can opt in to auto-apply recommendations from a specific source (e.g., "always auto-apply refund pairing suggestions"). This is opt-in and per-source, never global.

---

## Sources

| Source | What it recommends |
|--------|-------------------|
| Debt engine | Budget line adjustments, extra payment allocation |
| Goal engine | Contribution adjustments, funding source changes |
| Recurrence detector | New recurrence confirmations, deviation acknowledgments |
| Refund pairing | Pair a credit to a prior debit |
| Transfer detection | Pair two transactions as a transfer |
| AI insights | Anomaly responses, pattern-based suggestions, categorization assistance |
| Classification pipeline | Category suggestions for un-matched transactions (suggest mode) |

---

## Audit Trail

When a recommendation is accepted, its `rationale` field carries forward to the audit log entry for the resulting change. This makes every automated change traceable to its origin. See [data-layer.md](data-layer.md) — Audit Log.

---

## Reversibility

Every change applied through the recommendation system is reversible by the user. Reversal writes a new audit event. History is appended, never mutated.
