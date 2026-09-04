"""add rbac models and user role relationship

Revision ID: b2d3f4a5c6e7
Revises: ced3669ab116
Create Date: 2026-07-21 17:25:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2d3f4a5c6e7"
down_revision: Union[str, Sequence[str], None] = "ced3669ab116"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_index(
        op.f("ix_roles_id"),
        "roles",
        ["id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_roles_name"),
        "roles",
        ["name"],
        unique=False,
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_index(
        op.f("ix_permissions_id"),
        "permissions",
        ["id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_permissions_name"),
        "permissions",
        ["name"],
        unique=False,
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
        ),
        sa.PrimaryKeyConstraint(
            "role_id",
            "permission_id",
        ),
    )

    with op.batch_alter_table("users") as batch_op:

        batch_op.add_column(
            sa.Column(
                "role_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_foreign_key(
            "fk_users_role_id_roles",
            "roles",
            ["role_id"],
            ["id"],
        )


def downgrade() -> None:

    with op.batch_alter_table("users") as batch_op:

        batch_op.drop_constraint(
            "fk_users_role_id_roles",
            type_="foreignkey",
        )

        batch_op.drop_column("role_id")

    op.drop_table("role_permissions")

    op.drop_index(
        op.f("ix_permissions_name"),
        table_name="permissions",
    )

    op.drop_index(
        op.f("ix_permissions_id"),
        table_name="permissions",
    )

    op.drop_table("permissions")

    op.drop_index(
        op.f("ix_roles_name"),
        table_name="roles",
    )

    op.drop_index(
        op.f("ix_roles_id"),
        table_name="roles",
    )

    op.drop_table("roles")
