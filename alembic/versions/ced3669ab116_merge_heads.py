"""merge heads

Revision ID: ced3669ab116
Revises: 45d2f5a2e535, f1e2d3c4b5a6
Create Date: 2026-07-21 16:44:51.679759

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ced3669ab116'
down_revision: Union[str, Sequence[str], None] = ('45d2f5a2e535', 'f1e2d3c4b5a6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
