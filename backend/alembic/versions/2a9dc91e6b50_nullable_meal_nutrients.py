"""Preserve unknown meal nutrient totals as NULL.

Revision ID: 2a9dc91e6b50
Revises: 763081946f7a
"""
from alembic import op
import sqlalchemy as sa

revision = "2a9dc91e6b50"
down_revision = "763081946f7a"
branch_labels = None
depends_on = None

def upgrade():
    for column in ("kcal", "protein", "carbs", "fat"):
        op.alter_column("meals", column, existing_type=sa.Float(), nullable=True)

def downgrade():
    op.execute("UPDATE meals SET kcal=0 WHERE kcal IS NULL")
    op.execute("UPDATE meals SET protein=0 WHERE protein IS NULL")
    op.execute("UPDATE meals SET carbs=0 WHERE carbs IS NULL")
    op.execute("UPDATE meals SET fat=0 WHERE fat IS NULL")
    for column in ("kcal", "protein", "carbs", "fat"):
        op.alter_column("meals", column, existing_type=sa.Float(), nullable=False)
