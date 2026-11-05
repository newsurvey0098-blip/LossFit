"""Persist owner-scoped previews and confirmation audit for assistant actions."""
from alembic import op
import sqlalchemy as sa

revision = "b13dc8f20a61"
down_revision = "a76c4b8e2109"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_actions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("preview", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["assistant_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_assistant_action_owner_key"),
    )
    op.create_index("ix_assistant_actions_owner_id", "assistant_actions", ["owner_id"])
    op.create_index("ix_assistant_actions_conversation_id", "assistant_actions", ["conversation_id"])


def downgrade():
    op.drop_index("ix_assistant_actions_conversation_id", table_name="assistant_actions")
    op.drop_index("ix_assistant_actions_owner_id", table_name="assistant_actions")
    op.drop_table("assistant_actions")
