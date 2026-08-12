"""add local session id for agent sync

Revision ID: 2fa88ddac5a7
Revises: a35cf98ce6cc
Create Date: 2026-08-07 12:50:53.070551
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2fa88ddac5a7"
down_revision: Union[str, Sequence[str], None] = "a35cf98ce6cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add client/local session mapping to server sessions."""

    with op.batch_alter_table("sessions") as batch_op:

        batch_op.add_column(
            sa.Column(
                "local_session_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_sessions_device_id",
            ["device_id"],
            unique=False,
        )

        batch_op.create_unique_constraint(
            "uq_sessions_device_local_session",
            [
                "device_id",
                "local_session_id",
            ],
        )


def downgrade() -> None:
    """Remove client/local session mapping."""

    with op.batch_alter_table("sessions") as batch_op:

        batch_op.drop_constraint(
            "uq_sessions_device_local_session",
            type_="unique",
        )

        batch_op.drop_index(
            "ix_sessions_device_id",
        )

        batch_op.drop_column(
            "local_session_id",
        )
