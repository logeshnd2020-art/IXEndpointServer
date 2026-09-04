"""add local application id for agent sync

Revision ID: 9576d988b066
Revises: 2fa88ddac5a7
Create Date: 2026-08-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9576d988b066"
down_revision: Union[str, Sequence[str], None] = "2fa88ddac5a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add client/local application mapping."""

    with op.batch_alter_table("applications") as batch_op:

        batch_op.add_column(
            sa.Column(
                "local_application_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_applications_device_id",
            ["device_id"],
            unique=False,
        )

        batch_op.create_index(
            "ix_applications_session_id",
            ["session_id"],
            unique=False,
        )

        batch_op.create_unique_constraint(
            "uq_applications_device_local_application",
            [
                "device_id",
                "local_application_id",
            ],
        )


def downgrade() -> None:
    """Remove client/local application mapping."""

    with op.batch_alter_table("applications") as batch_op:

        batch_op.drop_constraint(
            "uq_applications_device_local_application",
            type_="unique",
        )

        batch_op.drop_index(
            "ix_applications_session_id",
        )

        batch_op.drop_index(
            "ix_applications_device_id",
        )

        batch_op.drop_column(
            "local_application_id",
        )
