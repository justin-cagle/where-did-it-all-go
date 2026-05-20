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

## API Endpoints

All routes scoped under `/api/v1/households/{household_id}/insights/`.

### Provider Config

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/providers` | List `InsightProviderConfig` records for household |
| `POST` | `/providers` | Add new provider config |
| `PATCH` | `/providers/{config_id}` | Update config (enable/disable, model, credentials, base_url) |
| `DELETE` | `/providers/{config_id}` | Soft-delete (sets `archived_at`) |
| `POST` | `/providers/{config_id}/test` | Test provider availability — always returns 200, never raises on connection failure. Returns `{available, model_name, error}` |

### Ollama Model Management

These routes proxy directly to the Ollama HTTP API on the configured `base_url`. They require an active (non-archived) `local_ollama` provider config — return 400 if none exists.

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/providers/ollama/models` | List installed models. Returns `{models: [{name, size_bytes, modified_at}]}`. Returns empty list (not error) if Ollama unreachable. |
| `POST` | `/providers/ollama/pull` | Pull a model. Body: `{model_name}`. Streams SSE progress events (`data: {status, completed?, total?}\n\n`). `timeout=None` intentional — pulls can take many minutes. |
| `DELETE` | `/providers/ollama/models/{model_name:path}` | Delete an installed model. `model_name` is URL-encoded (colons encoded as `%3A`). Returns 204 on success. |

**Route registration order:** Ollama-specific literal routes must be registered before `/{config_id}` parameterized routes.

### Budget

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/budget` | Get or create current period `TokenBudget` |
| `PATCH` | `/budget` | Update `token_limit`, `cost_limit`, `currency`, `overage_behavior` |

### Audit & Q&A

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/audit` | Paginated `InsightAuditLog`. Params: `limit` (1-200, default 50), `offset` |
| `POST` | `/ask` | Synchronous Q&A. Body: `{question}`. Rate-limited 10/min per household. Returns `{answer, provider_used, reason}` |
| `POST` | `/generate` | Enqueue insight generation ARQ job. Returns `{job_id}`. 202 Accepted. |

---

## Frontend UX

### Settings Page (`InsightsSettingsPage`)

**Connection status** — each provider row shows a live status chip:

| State | Display |
|-------|---------|
| `untested` | Gray dot — "Not tested" |
| `testing` | Spinner — "Testing..." |
| `connected` | Green dot — "Connected · {model_name}" |
| `unreachable` | Red dot — "Unreachable" |

Enabled providers are auto-tested in parallel on page mount via `useEffect`. Clicking the chip re-runs the test.

**Save/delete feedback** — inline error message below the action area on failure; 3-second success flash on save. Modal stays open on add error.

**OllamaModelSelector** — when `providerType === 'local_ollama'` and `baseUrl` is set, shows installed model names in a `<select>` dropdown (populated from `GET /providers/ollama/models`). Falls back to free-text input if Ollama is unreachable.

**OllamaModelManager sheet** — slide-in panel (fixed overlay, 480px wide) triggered by "Manage models" button:
- Installed model list: name (monospace), size via `formatBytes()`, relative modified date, "Use" button (calls `onModelSelected`), delete with inline confirm
- Pull form: text input + "Pull model" button + "Browse models at ollama.com/library" external link
- SSE pull progress via `fetch` + `ReadableStream` + `TextDecoder` (not `EventSource` — endpoint is POST)
- Progress bar for downloading phase; status text for other phases
- Inline error with Retry button on pull failure

### Insights Page (`InsightsPage`)

**Provider status bar** — chips per enabled provider, each auto-tested on mount. Chip color follows connection state.

**Q&A errors** — typed messages per `reason` field:

| reason | Message |
|--------|---------|
| `no_provider` | "No AI provider configured" + Settings link |
| `budget_exceeded` | "Monthly AI budget reached" + Settings link |
| `disabled` | "AI provider disabled" + Settings link |
| *(other)* | Generic error message |

**In-flight UX** — textarea disabled while request in flight; button shows "Thinking..." + spinner. 60s informational warning banner if no response yet (uses `setTimeout` ref — does NOT cancel the request). No automatic timeout on the request itself.

**All-disabled warning** — banner above Q&A input when all configured providers have `enabled=false`.

**Generate button** — 60s disable after trigger (tracked via `disabledUntil` timestamp). Shows toast on enqueue. Inline error on failure.

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
