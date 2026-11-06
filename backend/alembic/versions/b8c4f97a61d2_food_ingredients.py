"""Store recorded food ingredients for cautious recommendations."""
from alembic import op
import sqlalchemy as sa

revision = "b8c4f97a61d2"
down_revision = "a59e1d370cf2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("foods", sa.Column("ingredients", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("foods", "ingredients")
