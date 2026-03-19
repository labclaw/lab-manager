"""add usage_events table

Revision ID: 4266dbc78c53
Revises: 4ecede3a6f58
Create Date: 2026-03-19 17:22:20.117999

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '4266dbc78c53'
down_revision: Union[str, None] = '4ecede3a6f58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'usage_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('page', sa.String(length=500), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_usage_events_user_email', 'usage_events', ['user_email'])
    op.create_index('ix_usage_events_event_type', 'usage_events', ['event_type'])
    op.create_index('ix_usage_events_user_ts', 'usage_events', ['user_email', 'timestamp'])
    op.create_index('ix_usage_events_type_ts', 'usage_events', ['event_type', 'timestamp'])


def downgrade() -> None:
    op.drop_index('ix_usage_events_type_ts', table_name='usage_events')
    op.drop_index('ix_usage_events_user_ts', table_name='usage_events')
    op.drop_index('ix_usage_events_event_type', table_name='usage_events')
    op.drop_index('ix_usage_events_user_email', table_name='usage_events')
    op.drop_table('usage_events')
