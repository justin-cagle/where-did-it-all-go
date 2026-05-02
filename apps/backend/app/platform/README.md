# platform

Shared foundation for all domain modules. Contains no business logic.

## Ownership

Money/Decimal handling · FX rate management · time abstractions · UUIDs · common types

## Public Interface

_(populated as utilities are added)_

## Constraints

- All domain modules **may** import from `platform`.
- `platform` **must not** import from any domain module (enforced by import-linter).

## Emitted Events

None.

## Consumed Events

None.
