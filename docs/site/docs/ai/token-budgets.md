# Token Budgets

## What tokens are

When you send a question to an AI provider, the text is broken into small chunks called **tokens** (roughly one token per 3–4 characters of text). The AI reads those tokens and generates a response made of more tokens. Cloud AI providers (Anthropic, OpenAI) charge by the number of tokens processed.

For local providers (Ollama, llama.cpp), there's no per-token cost — but setting a token budget still limits computation time.

## Setting a token limit

In **Settings → AI → Token Budget**, set a monthly token limit. Once the limit is reached, AI requests stop (by default) until the next month.

Token limits are per household, not per user.

## Setting a cost limit

Set a monthly cost limit in your home currency. WDIAG tracks the estimated cost of each AI request (provider rate × tokens used) and stops requests when the limit is reached.

Cost tracking is an estimate — actual billing from your provider may differ slightly from WDIAG's estimate.

## Overage behavior

What happens when a limit is reached:

| Mode | Behavior |
|------|---------|
| **Block** (default) | AI requests are refused. Users see "AI budget reached for this month." |
| **Warn and continue** | A warning is logged, the request proceeds anyway |
| **Silent** | The request proceeds without any warning |

Change overage behavior in Settings → AI → Token Budget.

## Monitoring usage

The AI section of your settings shows usage for the current month:
- Tokens used / limit
- Estimated cost / limit (if a cost limit is set)
- Breakdown by provider, model, and insight category (anomaly detection, Q&A, categorization assistance, etc.)

## Why budgets exist

Cloud AI providers charge real money. A household running active AI insights and asking frequent questions can accumulate noticeable API costs over a month. The default `block` behavior ensures you don't get surprised at the end of the month.

For local providers, there's no direct cost, but you can still set a token budget to limit how much AI computation runs (relevant on low-power servers where AI inference competes with other resources).

If you're using a local model only and have no cost concerns, you can set no limit at all — just don't configure a budget.
