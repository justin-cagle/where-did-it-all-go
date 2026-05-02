# Security

> Source: `DECISIONS.md` — R4E (Security)

---

## Core Rule

**Use established, audited libraries for security-critical functionality.** Never roll custom auth, encryption, or token handling when a well-maintained library exists. Security code is never vibe-coded without expert review.

Required libraries:

| Purpose | Library |
|---------|---------|
| Password hashing | `passlib` / `argon2-cffi` |
| JWT | `python-jose` or `authlib` |
| Encryption | `cryptography` |
| OIDC client | `authlib` |

---

## Encryption at Rest (Application-Layer)

Full-DB encryption is not used. Instead, specific sensitive fields are encrypted at the application layer:

- Account numbers and routing numbers
- Aggregator credentials (SimpleFIN tokens, OFX credentials)
- OIDC tokens
- AI provider API keys

**Aggregator credentials additional rules:** never logged, never sent to AI providers, encrypted at rest, and rotatable without re-entering user credentials.

---

## Master Key Custody

User-configurable per deployment. The app refuses to start if the configured mode is not satisfiable.

| Mode | Notes |
|------|-------|
| `env_var` | Simplest; weakest — key lives in the process environment |
| `file` | File path; app checks permissions at startup |
| `vault` | Pluggable backend: HashiCorp Vault, Infisical, sops/age, AWS Secrets Manager |

**Key rotation:** periodic re-encryption with a new master key is supported. A leaked old key does not compromise data encrypted after rotation.

**Re-key procedure:** decrypt with old key, re-encrypt with new key. Supports migration between custody modes.

**Breach detection logging:** failed decryption attempts are logged and trigger an alert. If something is attempting keys against encrypted fields, the system surfaces it.

---

## Threat Model (Documented)

Application-layer encryption protects against **DB file theft** — an attacker who obtains the database file without the master key cannot read sensitive fields.

It does **not** protect against full host compromise, where an attacker obtains both the DB and the master key. For that threat, use `vault` mode with separate secrets infrastructure.

This threat model is explicitly documented in the app's deployment documentation, not hidden in code.

---

## Step-Up Authentication

The following App Admin actions require step-up auth — re-enter password **or** TOTP confirmation:

- Adding a household member
- Changing encryption keys
- Exporting full household data

Standard Owner financial actions (viewing transactions, editing budgets, managing goals) remain session-authenticated with no step-up.

---

## Read-Only Panic Switch

A toggle that disables all writes including aggregator sync, without taking the app down. Used when the user suspects a sync issue or wants to freeze state for investigation.

---

## Privacy Viewing Mode

Per-device/session toggle (not per household). Two modes:

| Mode | Display |
|------|---------|
| `full_blur` | All monetary amounts shown as `••••` |
| `partial_blur` | Amounts shown as `$•,•••` (magnitude visible, exact value hidden) |

Applied universally via the `formatAmount()` function — every component displaying money goes through this function.

**Does not apply to:** category names, merchant names, dates.

---

## Backup

- Nightly logical Postgres dump.
- Encrypted with a separate backup key (distinct from the master key).
- Storage: local volume (always) + optional S3-compatible upload (MinIO, B2, S3, R2, Wasabi).
- Env vars: `BACKUP_S3_ENDPOINT`, `BACKUP_S3_BUCKET`, `BACKUP_S3_ACCESS_KEY`, `BACKUP_S3_SECRET_KEY`, `BACKUP_ENCRYPTION_KEY`.
- Restoration tool ships with the app: `python -m app.backup restore <file>`.
- **Restore procedure is tested in CI against a known-good snapshot.** A procedure not tested is not a procedure.
