"""Persist owner-scoped food favorites and recently viewed foods."""
from alembic import op
import sqlalchemy as sa

revision = "019fa2c83d72"
down_revision = "d702c2c643a1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "food_favorites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "food_id", name="uq_food_favorite_owner_food"),
    )
    op.create_index("ix_food_favorites_owner_id", "food_favorites", ["owner_id"])
    op.create_index("ix_food_favorites_food_id", "food_favorites", ["food_id"])
    op.create_table(
        "food_recents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "food_id", name="uq_food_recent_owner_food"),
    )
    op.create_index("ix_food_recents_owner_id", "food_recents", ["owner_id"])
    op.create_index("ix_food_recents_food_id", "food_recents", ["food_id"])
    op.create_index("ix_food_recents_viewed_at", "food_recents", ["viewed_at"])


def downgrade():
    op.drop_index("ix_food_recents_viewed_at", table_name="food_recents")
    op.drop_index("ix_food_recents_food_id", table_name="food_recents")
    op.drop_index("ix_food_recents_owner_id", table_name="food_recents")
    op.drop_table("food_recents")
    op.drop_index("ix_food_favorites_food_id", table_name="food_favorites")
    op.drop_index("ix_food_favorites_owner_id", table_name="food_favorites")
    op.drop_table("food_favorites")
