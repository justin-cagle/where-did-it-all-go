# Privacy Levels

The privacy level controls what data is sent to an AI provider when generating insights or answering questions. This is a security-critical setting — choose it carefully.

## The five levels

### disabled — "Nothing sent"

No data is sent to any AI provider. The AI subsystem is completely off. This is the right choice if you don't want any AI features.

**What leaves your server:** nothing.

### generalizations_only — "Category names and patterns, no amounts, no merchants"

Abstract patterns only. The AI sees high-level behavioral summaries — "spending in category X increased this month" — with no specific amounts, no merchant names, and no dates beyond period granularity.

**What leaves your server:** abstract spending patterns, category names, period-level trends.  
**What does NOT leave:** amounts, merchant names, account names, exact dates, or any identifying information.

**This is the default for all cloud providers (Anthropic, OpenAI).** It cannot be set lower than this for cloud providers.

### aggregates_only — "Category totals and stats, no individual transactions"

Category-level spending totals and aggregate statistics. Amounts are included at the category level. Merchant names are one-way hashed (cannot be reversed by anyone, including Anthropic or OpenAI).

**What leaves your server:** category totals, aggregate amounts, hashed merchant names.  
**What does NOT leave:** individual transaction amounts, raw merchant names, account numbers, income source identities.

### redacted — "Transaction structure, amounts, hashed merchants"

Transaction-level data with personally identifiable information removed. Individual transaction amounts are included. Account numbers, full transaction descriptions, and income source identities are stripped.

**What leaves your server:** transaction amounts and dates, hashed merchant names, transaction types (payroll/grocery/dining/etc.).  
**What does NOT leave:** account numbers, full descriptions, income source names.

### full — "Everything — local providers only"

All data, unsanitized. Only available for local providers (Ollama, llama.cpp). **Hard-blocked for cloud providers (Anthropic, OpenAI) regardless of user setting.** Even if you set `full` for a cloud provider in configuration, it will never be sent — the redaction layer enforces this in code.

**What leaves your server:** complete transaction history, all amounts, all merchant names, all account balances.  
**What does NOT leave:** anything (everything stays on your server with a local model).

## What "hashed merchant" means

A hashed merchant name is a one-way transformation. "Target" might become `a7f3bc...`. The AI provider sees a consistent identifier for each merchant (useful for patterns — "you spent at [merchant-hash-x] 12 times this month") without seeing the actual name.

This hash cannot be reversed — not by the AI provider, not by us, not by anyone. It's a one-way function applied before any data leaves your server.

## Choosing a level

For **cloud providers** (Anthropic, OpenAI):
- `generalizations_only` is the default — safe for most use cases, gives useful high-level insights
- `aggregates_only` allows some amount-level insights if you're comfortable with category totals leaving your server
- `redacted` gives the AI more to work with but sends individual transaction amounts

For **local providers** (Ollama, llama.cpp):
- `full` is available and recommended — data never leaves your server at any privacy level
- Setting a lower level is possible if you want to limit what the local model can see

## Why full is blocked for cloud providers

Sending your complete financial transaction history to a cloud API provider — even a privacy-conscious one — is a significant data exposure. WDIAG enforces this at the application layer, not just via documentation. Even if you deliberately set `full` for a cloud provider, the redaction layer will cap it at `redacted`. This is not configurable.

If you want `full` access to your data for AI, use a local model.
