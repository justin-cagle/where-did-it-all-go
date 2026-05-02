# insights

## Ownership

InsightProvider abstraction · redaction layer (security-critical) · prompt templates · response handling · token/cost budget management

## Providers

LocalOllama · LocalLlamaCpp · Anthropic · OpenAI · Disabled

## Privacy Levels (ai_data_sharing)

disabled · generalizations_only (default for remote) · aggregates_only · redacted · full (local only)

## Constraints

- LLM never touches the database directly.
- Insight outputs are Recommendation objects, routed through HITL.
- AI is never on the critical path.

## Public Interface

_(populated as the module is built)_

## Emitted Events

Recommendation objects only.

## Consumed Events

_(populated as the module is built)_
