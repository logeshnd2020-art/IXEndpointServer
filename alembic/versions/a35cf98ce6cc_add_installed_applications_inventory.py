"""add installed applications inventory

Revision ID: a35cf98ce6cc
Revises: 689de6944022
Create Date: 2026-08-06 19:00:12.015932
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a35cf98ce6cc"
down_revision: Union[str, Sequence[str], None] = "689de6944022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create installed applications inventory table."""

    op.create_table(
        "installed_applications",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "device_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "version",
            sa.String(length=100),
            nullable=True,
        ),

        sa.Column(
            "bundle_id",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "install_path",
            sa.String(length=500),
            nullable=True,
        ),

        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),

        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),

        sa.Column(
            "is_installed",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
        ),

        sa.PrimaryKeyConstraint("id"),

        sa.UniqueConstraint(
            "device_id",
            "name",
            "install_path",
            name="uq_installed_app_device_name_path",
        ),
    )

    op.create_index(
        "ix_installed_applications_device_id",
        "installed_applications",
        ["device_id"],
        unique=False,
    )

    op.create_index(
        "ix_installed_applications_id",
        "installed_applications",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove installed applications inventory table."""

    op.drop_index(
        "ix_installed_applications_id",
        table_name="installed_applications",
    )

    op.drop_index(
        "ix_installed_applications_device_id",
        table_name="installed_applications",
    )

    op.drop_table("installed_applications")
