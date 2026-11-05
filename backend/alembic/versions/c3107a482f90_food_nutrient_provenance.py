"""Retain per-nutrient provenance and import quality notes."""
from alembic import op
import sqlalchemy as sa

revision = "c3107a482f90"
down_revision = "b17e9c04a521"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("foods", sa.Column("nutrition_provenance", sa.JSON(), server_default=sa.text("'{}'"), nullable=False))
    op.add_column("foods", sa.Column("data_notes", sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column("foods", "data_notes")
    op.drop_column("foods", "nutrition_provenance")
