"""Retain recipe ingredient snapshots and finished yield."""
from alembic import op
import sqlalchemy as sa
revision='c27f8e914a52'
down_revision='b13dc8f20a61'
branch_labels=None
depends_on=None
def upgrade():op.add_column('foods',sa.Column('recipe',sa.JSON(),nullable=True))
def downgrade():op.drop_column('foods','recipe')
