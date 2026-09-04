"""fix sqlite timestamp defaults

Revision ID: 689de6944022
Revises: e4f5a6b7c8d9
"""

from alembic import op
import sqlalchemy as sa


revision = "689de6944022"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:

    # sessions
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.alter_column(
            "login_time",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            existing_nullable=False,
        )

    # applications
    with op.batch_alter_table("applications") as batch_op:
        batch_op.alter_column(
            "start_time",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            existing_nullable=False,
        )

    # idle_events
    with op.batch_alter_table("idle_events") as batch_op:
        batch_op.alter_column(
            "idle_start",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            existing_nullable=False,
        )

    # activity_events
    with op.batch_alter_table("activity_events") as batch_op:
        batch_op.alter_column(
            "captured_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            existing_nullable=False,
        )

    # users
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            existing_nullable=False,
        )

    # devices
    with op.batch_alter_table("devices") as batch_op:
        for column in ("last_seen", "created_at", "updated_at"):
            batch_op.alter_column(
                column,
                existing_type=sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                existing_nullable=True,
            )

    # enrollment_keys
    with op.batch_alter_table("enrollment_keys") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            existing_nullable=True,
        )

    # device_heartbeats
    with op.batch_alter_table("device_heartbeats") as batch_op:
        batch_op.alter_column(
            "timestamp",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            existing_nullable=False,
        )

    # device_telemetry
    with op.batch_alter_table("device_telemetry") as batch_op:
        batch_op.alter_column(
            "timestamp",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            existing_nullable=False,
        )


def downgrade() -> None:
    pass
