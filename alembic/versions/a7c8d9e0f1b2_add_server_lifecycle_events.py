"""add server_lifecycle_events table

Revision ID: a7c8d9e0f1b2
Revises: d4e5f6a7b8c9
Create Date: 2026-09-07

Phase 3, Item 2 -- durable, additive record of this server process's
own startup/shutdown lifecycle. See app.models.server_lifecycle_event
for the full evidence-conservatism rationale: a clean shutdown reliably
writes a row, but a crash/hard reboot/power loss/SIGKILL does not, so
absence of a shutdown row must never be read as proof of continuous
availability.

Purely additive -- creates one new table, touches nothing existing.
Idempotent: skips creation if the table already exists.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c8d9e0f1b2"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Create server_lifecycle_events if it does not already exist."""

    if _has_table("server_lifecycle_events"):
        return

    op.create_table(
        "server_lifecycle_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("pid", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_server_lifecycle_events_id",
        "server_lifecycle_events",
        ["id"],
    )


def downgrade() -> None:
    """Drop server_lifecycle_events if it is present."""

    if not _has_table("server_lifecycle_events"):
        return

    op.drop_index(
        "ix_server_lifecycle_events_id",
        table_name="server_lifecycle_events",
    )
    op.drop_table("server_lifecycle_events")
