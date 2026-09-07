"""add unique constraint on idle_events(device_id, local_idle_id)

Revision ID: c9e0f1a2b3d4
Revises: b8d9e0f1a2c3
Create Date: 2026-09-07

Phase 3, Item 5 -- closes the one inconsistency in the existing
local_*_id idempotency pattern: sessions.local_session_id and
applications.local_application_id already have (device_id, local_*_id)
uniqueness enforced; idle_events.local_idle_id existed as a plain
column with no constraint.

Verified read-only against production data before writing this
migration: zero existing rows have a NULL local_idle_id, and zero
duplicate (device_id, local_idle_id) pairs exist, so this constraint
can be added with no data cleanup step. Re-verify both counts
immediately before actually applying this migration to production,
since new idle-sync traffic may have arrived since this check.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9e0f1a2b3d4"
down_revision: Union[str, Sequence[str], None] = "b8d9e0f1a2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT_NAME = "uq_idle_events_device_local_idle"


def _has_constraint(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    names = {
        uc["name"]
        for uc in inspector.get_unique_constraints(table_name)
    }
    return constraint_name in names


def upgrade() -> None:
    """Add the unique constraint if it is not already present."""

    if _has_constraint("idle_events", CONSTRAINT_NAME):
        return

    with op.batch_alter_table("idle_events") as batch_op:
        batch_op.create_unique_constraint(
            CONSTRAINT_NAME,
            ["device_id", "local_idle_id"],
        )


def downgrade() -> None:
    """Remove the unique constraint if present."""

    if not _has_constraint("idle_events", CONSTRAINT_NAME):
        return

    with op.batch_alter_table("idle_events") as batch_op:
        batch_op.drop_constraint(CONSTRAINT_NAME, type_="unique")
