"""Add persistent abuse-control buckets.

Revision ID: e935c8021a6f
Revises: a402e0195bf1
"""
from alembic import op
import sqlalchemy as sa

revision = 'e935c8021a6f'
down_revision = 'a402e0195bf1'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'rate_limit_buckets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scope', sa.String(length=40), nullable=False),
        sa.Column('subject_digest', sa.String(length=64), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope', 'subject_digest', 'window_start', name='uq_rate_limit_bucket'),
    )
    op.create_index(op.f('ix_rate_limit_buckets_window_start'), 'rate_limit_buckets', ['window_start'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_rate_limit_buckets_window_start'), table_name='rate_limit_buckets')
    op.drop_table('rate_limit_buckets')
