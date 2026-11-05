"""Store private Google account links and one-time OAuth state."""
from alembic import op
import sqlalchemy as sa

revision = "a76c4b8e2109"
down_revision = "f6a981b44ac2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "google_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_subject", name="uq_google_account_subject"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "google_oauth_states",
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("code_verifier", sa.String(length=512), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("state_hash"),
    )
    op.create_index("ix_google_oauth_states_user_id", "google_oauth_states", ["user_id"])


def downgrade():
    op.drop_index("ix_google_oauth_states_user_id", table_name="google_oauth_states")
    op.drop_table("google_oauth_states")
    op.drop_table("google_accounts")
