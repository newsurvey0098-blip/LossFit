"""Recover refresh-token rotation when a navigation aborts the response."""
from alembic import op
import sqlalchemy as sa

revision = "a59e1d370cf2"
down_revision = "d18f3a94b211"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("auth_sessions", sa.Column("retry_token_hash", sa.String(length=64), nullable=True))
    op.add_column("auth_sessions", sa.Column("retry_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("auth_sessions", sa.Column("retry_current_token", sa.Text(), nullable=True))
    op.create_index("ix_auth_sessions_retry_token_hash", "auth_sessions", ["retry_token_hash"], unique=False)


def downgrade():
    op.drop_index("ix_auth_sessions_retry_token_hash", table_name="auth_sessions")
    op.drop_column("auth_sessions", "retry_current_token")
    op.drop_column("auth_sessions", "retry_until")
    op.drop_column("auth_sessions", "retry_token_hash")
