"""add unique constraint on portfolio metrics user_id date

Revision ID: 1279fcb9517c
Revises: 713cdb7ae451
Create Date: 2026-06-20 23:17:58.248291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1279fcb9517c'
down_revision: Union[str, Sequence[str], None] = '713cdb7ae451'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_portfolio_daily_metrics_user_date",
        "portfolio_daily_metrics",
        ["user_id", "date"],
    )
    op.create_unique_constraint(
        "uq_portfolio_monthly_metrics_user_date",
        "portfolio_monthly_metrics",
        ["user_id", "date"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_portfolio_daily_metrics_user_date",
        "portfolio_daily_metrics",
        type_="unique",
    )
    op.drop_constraint(
        "uq_portfolio_monthly_metrics_user_date",
        "portfolio_monthly_metrics",
        type_="unique",
    )