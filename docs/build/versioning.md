# Versioning & Extensibility

> Source: `DECISIONS.md` — R11 D8 (Versioning & Releases), R5 (Extensibility)

---

## SemVer — Criteria

| Bump | When |
|------|------|
| **MAJOR** (`X.0.0`) | Breaking change to: public REST API contract, plugin contract, database schema requiring manual upgrade intervention (no auto-migration), or data export format |
| **MINOR** (`0.X.0`) | New feature, new module, new endpoint, new plugin extension point, additive schema change (auto-migrated), new currency/aggregator/AI provider support |
| **PATCH** (`0.0.X`) | Bug fix, security fix, performance improvement, internal refactor with no observable change, doc-only change |

**Pre-1.0 caveat:** while in `0.x`, MINOR bumps may include breaking changes. These are explicitly called out in the changelog with migration notes. `1.0` is the commitment line for backward compatibility on the public API.

---

## Conventional Commits

Enforced on all commit messages:

```
feat:     new feature (MINOR bump candidate)
fix:      bug fix (PATCH)
chore:    maintenance, tooling
docs:     documentation only
breaking: breaking change (MAJOR bump candidate)
```

Changelog is auto-generated from commit history on release.

---

## Release Process

1. Tag the commit (`git tag v0.x.y`).
2. CI builds Docker images.
3. Images pushed to ghcr.io with version tag + `latest`.
4. GitHub Release created with auto-generated changelog.
5. Docs site updated.

---

## Plugin Contract (`pluggy`)

Extension points committed in v1:

| Extension point | Reference implementations |
|----------------|--------------------------|
| Auth providers | Local auth (username+password+TOTP), OIDC |
| Aggregator providers | SimpleFIN (reference) |
| Budget methods | All shipped methods |
| Debt strategies | All shipped strategies |
| Insight providers | LocalOllama, LocalLlamaCpp, Anthropic, OpenAI |
| Export formats | CSV, JSON |
| Statement parsers | OFX/QFX, CSV |

Auth is the **first committed plugin contract** — established in v1 with two reference implementations.

---

## Webhook Subsystem

Outbound delivery to user-configured URLs:
- Signed payloads (HMAC signature on each request).
- Retry-with-backoff on delivery failure.
- Dead-letter queue for permanently failed deliveries.
- Event schema parallels internal SSE events.

Design is committed. Ship timing is v1 or v1.x — see [principles.md](principles.md).

---

## Documentation

In-repo docs shipped alongside code:

| Doc | Location |
|-----|----------|
| README | `README.md` — intro, quickstart |
| Architecture & design | `docs/design/` — `DECISIONS.md`, ADRs |
| Build context | `docs/build/` — this directory |
| API reference | Auto-generated from OpenAPI spec |
| Per-module reference | `README.md` in each module directory |
| Contributing | `CONTRIBUTING.md` |

ADRs (Architecture Decision Records) capture subsequent decisions: numbered, dated, standard format (context / decision / consequences).
