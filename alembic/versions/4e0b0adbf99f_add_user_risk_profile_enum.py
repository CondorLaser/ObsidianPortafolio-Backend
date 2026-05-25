"""add user.risk_profile enum

Revision ID: 4e0b0adbf99f
Revises: 8178d68d5150
Create Date: 2026-05-25 09:32:10.570124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e0b0adbf99f'
down_revision: Union[str, Sequence[str], None] = '8178d68d5150'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


risk_profile_enum = sa.Enum(
    "conservative", "moderate", "aggressive", name="risk_profile"
)


def upgrade() -> None:
    """Upgrade schema."""
    risk_profile_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "user",
        sa.Column("risk_profile", risk_profile_enum, nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user", "risk_profile")
    risk_profile_enum.drop(op.get_bind(), checkfirst=True)
