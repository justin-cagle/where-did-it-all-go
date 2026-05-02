# security

## Ownership

Encryption key management · secret storage abstraction · privacy mode state

## Key Custody Modes

env_var · file · vault (pluggable: HashiCorp Vault, Infisical, sops/age, AWS Secrets Manager)

## Constraints

- Uses established, audited libraries only: `cryptography`, `python-jose`, `authlib`, `passlib[argon2]`.
- Never roll custom auth, encryption, or token handling.
- Aggregator credentials never logged, never sent to AI providers, encrypted at rest, rotatable.

## Public Interface

_(populated as the module is built)_

## Emitted Events

None.

## Consumed Events

None.
