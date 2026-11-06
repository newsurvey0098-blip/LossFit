"""Support private photos on user-created foods."""
from alembic import op
import sqlalchemy as sa

revision = "d18f3a94b211"
down_revision = "c27f8e914a52"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("foods", sa.Column("image_path", sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column("foods", "image_path")
