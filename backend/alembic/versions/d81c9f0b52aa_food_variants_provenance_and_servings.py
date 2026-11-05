"""Add food provenance fields, aliases, and portion servings.

Revision ID: d81c9f0b52aa
Revises: 7f83ad201c4a
"""
from alembic import op
import sqlalchemy as sa

revision = 'd81c9f0b52aa'
down_revision = '7f83ad201c4a'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('foods', sa.Column('brand', sa.String(length=120), nullable=True))
    op.add_column('foods', sa.Column('category', sa.String(length=80), nullable=True))
    op.add_column('foods', sa.Column('aliases', sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
    op.add_column('foods', sa.Column('source_record_id', sa.String(length=120), nullable=True))
    op.add_column('foods', sa.Column('source_url', sa.String(length=500), nullable=True))
    op.add_column('foods', sa.Column('nutrition_basis', sa.String(length=40), server_default='per_100g', nullable=False))
    op.add_column('foods', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table(
        'food_servings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('food_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('grams', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=20), server_default='user_provided', nullable=False),
        sa.CheckConstraint('grams > 0 AND grams <= 10000', name='ck_food_servings_grams'),
        sa.ForeignKeyConstraint(['food_id'], ['foods.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_food_servings_food_id'), 'food_servings', ['food_id'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_food_servings_food_id'), table_name='food_servings')
    op.drop_table('food_servings')
    op.drop_column('foods', 'updated_at')
    op.drop_column('foods', 'nutrition_basis')
    op.drop_column('foods', 'source_url')
    op.drop_column('foods', 'source_record_id')
    op.drop_column('foods', 'aliases')
    op.drop_column('foods', 'category')
    op.drop_column('foods', 'brand')
