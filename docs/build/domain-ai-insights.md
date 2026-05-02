# Domain — AI Insights

> Source: `DECISIONS.md` — R4C (AI Insights)

---

## Core Rule

**AI is additive. The app functions fully without any LLM.** AI is never on the critical path of categorization, budgets, projections, debt plans, goals, or any other core feature. AI provider failure or absence degrades gracefully to "no insights surfaced."

---

## Provider Abstraction

The `InsightProvider` interface has these implementations:

| Implementation | Notes |
|---------------|-------|
| `LocalOllama` | Ollama running in the compose stack or BYO |
| `LocalLlamaCpp` | llama.cpp local inference |
| `Anthropic` | Remote API (privacy restrictions apply — see below) |
| `OpenAI` | Remote API (privacy restrictions apply — see below) |
| `Disabled` | No AI; insights subsystem is a no-op |

`provider_priority` is configured per household as an ordered list. The system falls back gracefully if a provider is unavailable.

---

## Insight Categories

- Anomaly detection (unusual spending, sudden changes)
- Pattern surfacing (behavioral patterns the user hasn't noticed)
- Recommendation rationales (natural-language explanations of system recommendations)
- Question answering (user asks a natural language question; answered against actual data)
- Categorization assistance for un-rule-matched transactions (suggestion routed through HITL)
- Forecast narratives (plain-language summary of projection output)

---

## Architectural Rules (Non-Negotiable)

- **LLM never touches the database directly.** It receives structured data via tool calls or RAG-style retrieval and returns structured output. The application layer applies changes.
- **All insight outputs are `Recommendation` objects.** They route through the HITL queue like any other recommendation. See [domain-recommendations.md](domain-recommendations.md).
- **Audit trail on every LLM call:** provider, model, prompt template, prompt fingerprint (hash — not the full prompt), response, tokens consumed, cost, household. This is not optional.

---

## Privacy Levels (`ai_data_sharing`)

| Level | What leaves the box | Notes |
|-------|--------------------|----- |
| `disabled` | Nothing | No remote calls ever |
| `generalizations_only` | Abstract patterns only — no amounts, no merchants, no dates beyond period granularity | **DEFAULT for all remote providers** |
| `aggregates_only` | Category-level totals and aggregate stats; amounts allowed; merchant names redacted/hashed | |
| `redacted` | Transaction-level data with PII stripped (account numbers, full descriptions, income source identities) | |
| `full` | Everything | **Local providers only.** Hard-gated by provider type — a remote provider cannot be configured to `full`, regardless of user preference. |

The redaction layer is a dedicated subsystem with explicit tests per privacy level. Treated as security-critical code.

---

## Token / Cost Budget Management

Per household, configurable:

| Setting | Description |
|---------|-------------|
| `ai_token_budget` | Monthly token cap |
| `ai_cost_budget` | Monthly cost cap in home currency |

Before each provider call, the system checks remaining budget. Overage behavior (configurable):

| Mode | Behavior |
|------|----------|
| `block` | Refuse the call. **DEFAULT.** |
| `warn_and_continue` | Log a warning, proceed anyway |
| `silent` | Proceed without any warning |

Usage is tracked per provider, per model, per insight category. A usage dashboard is surfaced to the user.
