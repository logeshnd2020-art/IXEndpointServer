"""add agent_lifecycle_events table

Revision ID: d0e1f2a3b4c5
Revises: c9e0f1a2b3d4
Create Date: 2026-09-07

7.8.0 client evidence groundwork -- creates agent_lifecycle_events, the
durable server-side store for the nine raw client-observed event types
defined in the approved 7.8.0 specification (SLEEP, WAKE,
SHUTDOWN_OR_RESTART_IMMINENT, AGENT_STARTED, AGENT_STOPPED,
NETWORK_UNAVAILABLE, NETWORK_RECOVERED, SERVER_UNAVAILABLE,
SERVER_RECOVERED). See app.models.agent_lifecycle_event for the full
rationale.

Purely additive -- creates one new table, touches nothing existing.
Idempotent: skips creation if the table already exists.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9e0f1a2b3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Create agent_lifecycle_events if it does not already exist."""

    if _has_table("agent_lifecycle_events"):
        return

    op.create_table(
        "agent_lifecycle_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("event_uid", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "upload_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("agent_version", sa.String(length=20), nullable=True),
        sa.Column("boottime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("wake_reason", sa.String(length=20), nullable=True),
        sa.Column("reachability_target", sa.String(length=20), nullable=True),
        sa.Column("detail", sa.String(length=255), nullable=True),
        sa.UniqueConstraint(
            "device_id",
            "event_uid",
            name="uq_agent_lifecycle_events_device_event_uid",
        ),
    )
    op.create_index(
        "ix_agent_lifecycle_events_id",
        "agent_lifecycle_events",
        ["id"],
    )
    op.create_index(
        "ix_agent_lifecycle_events_device_id",
        "agent_lifecycle_events",
        ["device_id"],
    )


def downgrade() -> None:
    """Drop agent_lifecycle_events if it is present."""

    if not _has_table("agent_lifecycle_events"):
        return

    op.drop_index("ix_agent_lifecycle_events_device_id", table_name="agent_lifecycle_events")
    op.drop_index("ix_agent_lifecycle_events_id", table_name="agent_lifecycle_events")
    op.drop_table("agent_lifecycle_events")
