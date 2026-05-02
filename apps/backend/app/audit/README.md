# audit

## Ownership

AuditEvent log (append-only) · change capture · replay tooling

## Constraints

- The app DB role has INSERT but NOT UPDATE/DELETE on `audit_event`.
- Append-only is enforced at the database permission level, not just application logic.

## Public Interface

_(populated as the module is built)_

## Emitted Events

None (audit is a sink, not a source).

## Consumed Events

Change events from all modules.
