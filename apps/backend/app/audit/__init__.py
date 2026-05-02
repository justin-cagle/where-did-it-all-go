"""Audit module.

Owns: AuditEvent append-only log, change capture, replay tooling.

The app DB role has INSERT only on the audit_event table — no UPDATE, no DELETE.
This is enforced at the database level via a trigger (not just application policy).
"""

from app.audit.models import ActorType, AuditEvent, AuditOperation

__all__ = [
    "ActorType",
    "AuditEvent",
    "AuditOperation",
]
