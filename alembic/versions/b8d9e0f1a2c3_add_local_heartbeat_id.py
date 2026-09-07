"""add local_heartbeat_id to device_heartbeats

Revision ID: b8d9e0f1a2c3
Revises: a7c8d9e0f1b2
Create Date: 2026-09-07

Phase 3, Item 5 -- adds a nullable local_heartbeat_id column to
device_heartbeats, mirroring the existing local_session_id /
local_application_id / local_idle_id pattern used for agent-sync
idempotency. No uniqueness is enforced yet -- the currently deployed
7.7.9 agent never sends this field, so this column is present but
functionally inert until a future client actually populates it.
Purely additive. Idempotent: skips the add if the column already
exists.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8d9e0f1a2c3"
down_revision: Union[str, Sequence[str], None] = "a7c8d9e0f1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    """Add device_heartbeats.local_heartbeat_id if not already present."""

    if _has_column("device_heartbeats", "local_heartbeat_id"):
        return

    with op.batch_alter_table("device_heartbeats") as batch_op:
        batch_op.add_column(
            sa.Column(
                "local_heartbeat_id",
                sa.Integer(),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Remove device_heartbeats.local_heartbeat_id if present."""

    if not _has_column("device_heartbeats", "local_heartbeat_id"):
        return

    with op.batch_alter_table("device_heartbeats") as batch_op:
        batch_op.drop_column("local_heartbeat_id")
