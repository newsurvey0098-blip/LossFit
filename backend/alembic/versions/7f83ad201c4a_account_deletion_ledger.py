"""Retain a restricted account-deletion marker for backup restoration.

Revision ID: 7f83ad201c4a
Revises: 1531ea15d76b
"""
from alembic import op
import sqlalchemy as sa

revision = '7f83ad201c4a'
down_revision = '1531ea15d76b'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'account_deletion_ledger',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_digest', sa.String(length=64), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_account_deletion_ledger_email_digest'), 'account_deletion_ledger', ['email_digest'], unique=True)

def downgrade():
    op.drop_index(op.f('ix_account_deletion_ledger_email_digest'), table_name='account_deletion_ledger')
    op.drop_table('account_deletion_ledger')
