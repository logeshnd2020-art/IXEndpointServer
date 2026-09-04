"""add_device_uuid_to_devices

Revision ID: ddd11860e6c4
Revises: b2d3f4a5c6e7
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ddd11860e6c4"
down_revision: Union[str, Sequence[str], None] = "b2d3f4a5c6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    with op.batch_alter_table("devices") as batch_op:

        batch_op.add_column(
            sa.Column("device_uuid", sa.String(length=100), nullable=True)
        )

        batch_op.add_column(
            sa.Column("manufacturer", sa.String(length=100),
nullable=True)
        )

        batch_op.add_column(
            sa.Column("model", sa.String(length=100), nullable=True)
        )

        batch_op.add_column(
            sa.Column("platform", sa.String(length=100), nullable=True)
        )

        batch_op.add_column(
            sa.Column("os_name", sa.String(length=100), nullable=True)
        )

        batch_op.add_column(
            sa.Column("os_version", sa.String(length=100), nullable=True)
        )

        batch_op.add_column(
            sa.Column("processor", sa.String(length=100), nullable=True)
        )

        batch_op.add_column(
            sa.Column("memory_gb", sa.Float(), nullable=True)
        )

        batch_op.add_column(
            sa.Column("storage_gb", sa.Float(), nullable=True)
        )

        batch_op.add_column(
            sa.Column("status", sa.String(length=50), nullable=True)
        )

        batch_op.add_column(
            sa.Column("device_token_hash", sa.String(length=255),
nullable=True)
        )

        batch_op.add_column(
            sa.Column("token_created_at", sa.DateTime(timezone=True),
nullable=True)
        )

        batch_op.add_column(
            sa.Column("token_last_used", sa.DateTime(timezone=True),
nullable=True)
        )

        batch_op.add_column(
            sa.Column("registration_date", sa.DateTime(timezone=True),
nullable=True)
        )

        batch_op.add_column(
            sa.Column("registered_by", sa.String(length=100),
nullable=True)
        )

        batch_op.add_column(
            sa.Column(
                "is_registered",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

        batch_op.create_unique_constraint(
            "uq_devices_device_uuid",
            ["device_uuid"],
        )


def downgrade() -> None:

    with op.batch_alter_table("devices") as batch_op:

        batch_op.drop_constraint(
            "uq_devices_device_uuid",
            type_="unique",
        )

        batch_op.drop_column("is_registered")
        batch_op.drop_column("registered_by")
        batch_op.drop_column("registration_date")
        batch_op.drop_column("token_last_used")
        batch_op.drop_column("token_created_at")
        batch_op.drop_column("device_token_hash")
        batch_op.drop_column("status")
        batch_op.drop_column("storage_gb")
        batch_op.drop_column("memory_gb")
        batch_op.drop_column("processor")
        batch_op.drop_column("os_version")
        batch_op.drop_column("os_name")
        batch_op.drop_column("platform")
        batch_op.drop_column("model")
        batch_op.drop_column("manufacturer")
        batch_op.drop_column("device_uuid")
