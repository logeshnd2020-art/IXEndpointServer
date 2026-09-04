"""add mac_address to device_heartbeats

Revision ID: d4e5f6a7b8c9
Revises: c3a9f1e2b4d6
Create Date: 2026-09-03

Adds a nullable mac_address column to device_heartbeats, alongside the
existing ip_address/network_name columns. Intended to hold the primary
physical network interface's hardware MAC address (format
"XX:XX:XX:XX:XX:XX"), reported by the agent -- never computed or
inferred server-side. NULL means the agent hasn't reported one yet
(true for every heartbeat from the currently deployed agent, which does
not send this field). Idempotent: skips the add if the column already
exists.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3a9f1e2b4d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    """Add device_heartbeats.mac_address if it is not already present."""

    if _has_column("device_heartbeats", "mac_address"):
        return

    with op.batch_alter_table("device_heartbeats") as batch_op:
        batch_op.add_column(
            sa.Column(
                "mac_address",
                sa.String(length=17),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Remove device_heartbeats.mac_address if it is present."""

    if not _has_column("device_heartbeats", "mac_address"):
        return

    with op.batch_alter_table("device_heartbeats") as batch_op:
        batch_op.drop_column("mac_address")
