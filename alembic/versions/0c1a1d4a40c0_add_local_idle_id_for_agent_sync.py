"""add local idle id for agent sync

Revision ID: 0c1a1d4a40c0
Revises: 9576d988b066
Create Date: 2026-08-11 18:20:59.677639
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0c1a1d4a40c0"
down_revision: Union[str, Sequence[str], None] = "9576d988b066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add client/local idle mapping."""

    op.add_column(
        "idle_events",
        sa.Column(
            "local_idle_id",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove client/local idle mapping."""

    op.drop_column(
        "idle_events",
        "local_idle_id",
    )
