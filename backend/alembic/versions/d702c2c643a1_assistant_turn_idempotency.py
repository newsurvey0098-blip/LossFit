"""Persist assistant request keys to make retries return the original answer."""
from alembic import op
import sqlalchemy as sa

revision = "d702c2c643a1"
down_revision = "c3107a482f90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_turns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("prompt", sa.String(length=4000), nullable=False),
        sa.Column("answer", sa.String(length=8000), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["assistant_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "idempotency_key", name="uq_assistant_turn_conversation_key"),
    )
    op.create_index("ix_assistant_turns_conversation_id", "assistant_turns", ["conversation_id"])


def downgrade():
    op.drop_index("ix_assistant_turns_conversation_id", table_name="assistant_turns")
    op.drop_table("assistant_turns")
