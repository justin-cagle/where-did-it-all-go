"""Audit DB role enforcement — trigger-based append-only guarantee.

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-05-14 00:00:00.000000

Adds:
  - audit_event_immutable() trigger function
  - BEFORE UPDATE / BEFORE DELETE triggers on audit_event
    that raise an exception on any attempt to mutate or remove rows

This enforces the append-only invariant at the DB level independently of
application-layer logic. The app role must also have UPDATE/DELETE privileges
revoked — that is handled in deployment scripts (the role name is not known
at migration time).
"""

from __future__ import annotations

from alembic import op

revision = "c3d4e5f6a7b8"  # pragma: allowlist secret
down_revision = "b1c2d3e4f5a6"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_event_immutable()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_event rows are immutable: UPDATE and DELETE are not permitted'
                USING ERRCODE = 'restrict_violation';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_event_no_update
            BEFORE UPDATE ON audit_event
            FOR EACH ROW
            EXECUTE FUNCTION audit_event_immutable();
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_event_no_delete
            BEFORE DELETE ON audit_event
            FOR EACH ROW
            EXECUTE FUNCTION audit_event_immutable();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_event_no_delete ON audit_event;")
    op.execute("DROP TRIGGER IF EXISTS audit_event_no_update ON audit_event;")
    op.execute("DROP FUNCTION IF EXISTS audit_event_immutable();")
