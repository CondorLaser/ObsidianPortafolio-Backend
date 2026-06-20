"""create alerts table

Revision ID: 59532bf665af
Revises: 8a9932449e9f
Create Date: 2026-06-19 21:27:30.209866

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '59532bf665af'
down_revision: Union[str, Sequence[str], None] = '7abe19b6030f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'alerts',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.VARCHAR(), nullable=False),
        sa.Column('type', sa.VARCHAR(), nullable=False),
        sa.Column('trigger_field', sa.VARCHAR(), nullable=False, server_default=''),
        sa.Column('trigger_value', sa.NUMERIC(precision=20, scale=8), nullable=False),
        sa.Column('threshold_value', sa.NUMERIC(precision=20, scale=8), nullable=False),
        sa.Column('msg', sa.TEXT(), nullable=False),
        sa.Column('notified_at', postgresql.TIMESTAMP(), nullable=False),
        sa.Column('last_triggered', sa.DATE(), nullable=False),
        sa.Column('is_active', sa.BOOLEAN(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_read', sa.BOOLEAN(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', postgresql.TIMESTAMP(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['profiles.clerk_id'], name=op.f('fk_alerts_user'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('alerts_pkey')),
    )
    op.create_index(op.f('idx_alerts_notified_at'), 'alerts', ['notified_at'], unique=False)
    op.create_index(op.f('idx_alerts_user_active_type'), 'alerts', ['user_id', 'is_active', 'type'], unique=False)
    op.create_index(op.f('idx_alerts_user_id'), 'alerts', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('idx_alerts_user_id'), table_name='alerts')
    op.drop_index(op.f('idx_alerts_user_active_type'), table_name='alerts')
    op.drop_index(op.f('idx_alerts_notified_at'), table_name='alerts')
    op.drop_table('alerts')