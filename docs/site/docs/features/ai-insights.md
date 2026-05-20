# AI Insights

## What AI insights are (and aren't)

AI insights are **observations about your data**, not financial advice. WDIAG's AI can notice patterns, flag anomalies, summarize your projection in plain English, and answer questions about your spending — but it doesn't give investment advice, can't predict the future, and should never be the basis for major financial decisions.

The AI layer is also **entirely optional**. Every feature in WDIAG — budgets, goals, debt plans, projections, calendar — works fully without any AI. If you don't configure a provider, insights simply don't appear. Nothing else breaks.

## What AI can do

- **Anomaly detection** — "Your dining spending in March was 3x your usual amount."
- **Pattern surfacing** — "Your grocery spending increases by about 20% in November and December."
- **Forecast narratives** — "Based on your current trajectory, you'll pay off the car loan 4 months early."
- **Q&A** — ask questions in plain English: "How much did I spend on subscriptions last quarter?" or "Which category has grown the most in the last 6 months?"
- **Categorization assistance** — suggest categories for transactions the rules engine couldn't match (routed through the HITL queue for your review).

## Asking a question

In the Insights section, use the Q&A interface to type a natural language question. WDIAG passes your question along with relevant summarized data to the AI provider. The response is shown inline.

Rate limit: 10 questions per minute per household.

## Generated insights

The system periodically generates insights automatically — anomalies, patterns, and forecast summaries. These appear in the Insights feed. You can:

- **Accept** an insight (marks it as acknowledged, can be reviewed later)
- **Dismiss** an insight (removes it from the feed)
- Act on a suggestion via the HITL queue

## How to interpret suggestions

All AI suggestions are routed through the **Recommendation** system and the HITL queue. The AI proposes; you decide. Nothing is applied automatically without your review.

Treat AI suggestions as a starting point for investigation, not a final answer.

## Token budget

Every AI request costs tokens — units of text processed by the model. For cloud providers (Anthropic, OpenAI), tokens cost real money. WDIAG lets you set limits to prevent surprise costs.

See [Token Budgets](../ai/token-budgets.md) for configuration details.

## Privacy and data sent to AI

What gets sent to an AI provider depends on your configured **privacy level**. The default for all cloud providers is `generalizations_only` — abstract patterns, no amounts, no merchant names.

See [Privacy Levels](../ai/privacy.md) for a full breakdown of what each level sends.

## Setting up AI

See [AI Providers](../ai/providers.md) for setup instructions.
