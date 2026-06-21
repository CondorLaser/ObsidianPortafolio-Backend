"""add unique constraint on portfolio metrics user_id date

Revision ID: 438b0eb14291
Revises: 1279fcb9517c
Create Date: 2026-06-20 23:27:53.162336

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '438b0eb14291'
down_revision: Union[str, Sequence[str], None] = '1279fcb9517c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
