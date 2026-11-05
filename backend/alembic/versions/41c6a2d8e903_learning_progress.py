"""Persist per-user completion of versioned learning lessons."""
from alembic import op
import sqlalchemy as sa

revision = "41c6a2d8e903"
down_revision = "f20d6a781be3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lesson_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("lesson_slug", sa.String(length=80), nullable=False),
        sa.Column("lesson_version", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "lesson_slug", name="uq_lesson_progress_owner_slug"),
    )
    op.create_index(op.f("ix_lesson_progress_owner_id"), "lesson_progress", ["owner_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_lesson_progress_owner_id"), table_name="lesson_progress")
    op.drop_table("lesson_progress")
