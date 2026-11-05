"""Add revocable rotating refresh-token sessions.

Revision ID: f20d6a781be3
Revises: e935c8021a6f
"""
from alembic import op
import sqlalchemy as sa

revision = 'f20d6a781be3'
down_revision = 'e935c8021a6f'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'auth_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('refresh_token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_auth_sessions_user_id'), 'auth_sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_auth_sessions_refresh_token_hash'), 'auth_sessions', ['refresh_token_hash'], unique=True)

def downgrade():
    op.drop_index(op.f('ix_auth_sessions_refresh_token_hash'), table_name='auth_sessions')
    op.drop_index(op.f('ix_auth_sessions_user_id'), table_name='auth_sessions')
    op.drop_table('auth_sessions')
