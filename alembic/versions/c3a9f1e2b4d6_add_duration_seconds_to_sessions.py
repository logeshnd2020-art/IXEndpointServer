"""add duration_seconds to sessions

Revision ID: c3a9f1e2b4d6
Revises: 0c1a1d4a40c0
Create Date: 2026-09-02

Adds a nullable duration_seconds column to sessions, used to store the
agent-reported monitored-awake duration (wall time minus confirmed sleep
minus unknown gaps). Idempotent: skips the add if the column already
exists so it is safe to re-run against a database that was patched by
hand or partially migrated.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3a9f1e2b4d6"
down_revision: Union[str, Sequence[str], None] = "0c1a1d4a40c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns(table_name)}
    return column_name in columns


def upgrade() -> None:
    """Add sessions.duration_seconds if it is not already present."""

    if _has_column("sessions", "duration_seconds"):
        return

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "duration_seconds",
                sa.Integer(),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Remove sessions.duration_seconds if it is present."""

    if not _has_column("sessions", "duration_seconds"):
        return

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("duration_seconds")
