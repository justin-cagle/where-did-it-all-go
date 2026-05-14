"""Audit module.

Owns: AuditEvent append-only log, change capture, replay tooling.

The app DB role has INSERT only on the audit_event table — no UPDATE, no DELETE.
This is enforced at the database level via a trigger (see migration
20260514_0013_c3d4e5f6a7b8_audit_db_role_enforcement).

All other modules call audit.service.log() to write audit events. Direct
instantiation of AuditEvent outside this module is a boundary violation.
"""

from app.audit.models import ActorType, AuditEvent, AuditOperation

__all__ = [
    "ActorType",
    "AuditEvent",
    "AuditOperation",
]
