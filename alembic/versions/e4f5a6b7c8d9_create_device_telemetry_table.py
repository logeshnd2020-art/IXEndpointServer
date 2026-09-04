"""create device telemetry table

Revision ID: e4f5a6b7c8d9
Revises: 9a10b793949b
Create Date: 2026-07-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "9a10b793949b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_telemetry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("cpu_usage", sa.Float(), nullable=False),
        sa.Column("memory_usage", sa.Float(), nullable=False),
        sa.Column("disk_usage", sa.Float(), nullable=False),
        sa.Column("battery_level", sa.Integer(), nullable=False),
        sa.Column("logged_in_user", sa.String(length=100), nullable=True),
        sa.Column("hostname", sa.String(length=100), nullable=False),
        sa.Column("ip_address", sa.String(length=50), nullable=False),
        sa.Column("network_name", sa.String(length=100), nullable=True),
        sa.Column("agent_version", sa.String(length=100), nullable=False),
        sa.Column("uptime_seconds", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_device_telemetry_id"), "device_telemetry", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_device_telemetry_id"), table_name="device_telemetry")
    op.drop_table("device_telemetry")
