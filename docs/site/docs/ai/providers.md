# AI Providers

## Supported providers

WDIAG supports four AI provider types plus a disabled option:

| Provider | Type | Notes |
|----------|------|-------|
| **Local Ollama** | Local | Runs on your server or a nearby machine. No data leaves your infrastructure. |
| **Local llama.cpp** | Local | Alternative local inference server. |
| **Anthropic (Claude)** | Cloud | Remote API. Privacy level restricted — see [Privacy Levels](privacy.md). |
| **OpenAI** | Cloud | Remote API. Privacy level restricted — see [Privacy Levels](privacy.md). |
| **Disabled** | None | No AI. Insights subsystem is a no-op. Everything else works normally. |

## Configuring providers

Go to **Settings → AI** to configure providers. You can configure multiple providers — the system uses them in your configured priority order and falls back gracefully if one is unavailable.

For each provider, you specify:
- Provider type (Ollama, llama.cpp, Anthropic, OpenAI, Disabled)
- Connection details (URL for local, API key for cloud)
- Model name
- Privacy level (what data can be sent — see [Privacy Levels](privacy.md))

## Provider priority

The system evaluates your provider list in order. If the first provider is unavailable (can't connect, API error, token budget exceeded), it falls back to the next configured provider.

If all providers are unavailable, AI insights degrade gracefully — no error is shown to users, insights simply aren't generated. Everything else in WDIAG continues working normally.

## Recommended setup for privacy-first users

Use a local Ollama instance with a small-to-medium language model. No data leaves your server. Full privacy level is available (you can send complete transaction data to the model). No API costs.

See [Local Models](local-models.md) for setup instructions.

## Adding a provider

1. Go to **Settings → AI → Add Provider**
2. Choose the provider type
3. For cloud providers: enter your API key
4. For local providers: enter the server URL (e.g., `http://ollama:11434` for Ollama in the same compose stack)
5. Choose a model
6. Set your [privacy level](privacy.md)
7. Save

## Disabling AI entirely

Set the provider to **Disabled** (or simply don't configure any providers). The AI subsystem is a no-op — no insights are generated, no network calls are made, no UI sections appear for AI features.
