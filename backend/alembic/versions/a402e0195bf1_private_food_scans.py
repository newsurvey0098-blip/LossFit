"""Persist private scanner sessions and review candidates.

Revision ID: a402e0195bf1
Revises: d81c9f0b52aa
"""
from alembic import op
import sqlalchemy as sa

revision = 'a402e0195bf1'
down_revision = 'd81c9f0b52aa'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'scan_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('private_path', sa.String(length=500), nullable=False),
        sa.Column('candidates', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('meal_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['meal_id'], ['meals.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_scan_sessions_owner_id'), 'scan_sessions', ['owner_id'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_scan_sessions_owner_id'), table_name='scan_sessions')
    op.drop_table('scan_sessions')
