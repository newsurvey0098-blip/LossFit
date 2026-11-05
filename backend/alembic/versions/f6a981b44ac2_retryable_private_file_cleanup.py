"""Retain failed private upload deletions for operator retry."""
from alembic import op
import sqlalchemy as sa

revision = "f6a981b44ac2"
down_revision = "019fa2c83d72"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "private_file_cleanup",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("private_path", sa.String(length=500), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("private_file_cleanup")
