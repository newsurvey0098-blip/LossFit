"""initial schema

Revision ID: 763081946f7a
Revises: 
Create Date: 2026-11-05 23:16:34.569033
"""
from alembic import op
import sqlalchemy as sa

revision = '763081946f7a'
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("users",
        sa.Column("id",sa.Integer(),nullable=False),sa.Column("email",sa.String(320),nullable=False),
        sa.Column("name",sa.String(100),nullable=False),sa.Column("password_hash",sa.String(255),nullable=False),
        sa.Column("goals",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_users_email","users",["email"],unique=True)
    op.create_table("foods",
        sa.Column("id",sa.Integer(),nullable=False),sa.Column("owner_id",sa.Integer(),nullable=True),
        sa.Column("name",sa.String(160),nullable=False),sa.Column("state",sa.String(40),nullable=False),
        sa.Column("verification",sa.String(20),nullable=False),sa.Column("source",sa.String(300),nullable=True),
        sa.Column("kcal",sa.Float(),nullable=True),sa.Column("protein",sa.Float(),nullable=True),
        sa.Column("carbs",sa.Float(),nullable=True),sa.Column("fat",sa.Float(),nullable=True),
        sa.ForeignKeyConstraint(["owner_id"],["users.id"],ondelete="CASCADE"),sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_foods_owner_id","foods",["owner_id"])
    op.create_index("ix_foods_name","foods",["name"])
    op.create_table("meals",
        sa.Column("id",sa.Integer(),nullable=False),sa.Column("owner_id",sa.Integer(),nullable=False),
        sa.Column("name",sa.String(160),nullable=False),sa.Column("meal_type",sa.String(24),nullable=False),
        sa.Column("eaten_at",sa.DateTime(timezone=True),nullable=False),sa.Column("items",sa.JSON(),nullable=False),
        sa.Column("kcal",sa.Float(),nullable=True),sa.Column("protein",sa.Float(),nullable=True),
        sa.Column("carbs",sa.Float(),nullable=True),sa.Column("fat",sa.Float(),nullable=True),
        sa.ForeignKeyConstraint(["owner_id"],["users.id"],ondelete="CASCADE"),sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_meals_owner_id","meals",["owner_id"])
    op.create_table("water_entries",
        sa.Column("id",sa.Integer(),nullable=False),sa.Column("owner_id",sa.Integer(),nullable=False),
        sa.Column("ml",sa.Integer(),nullable=False),sa.Column("logged_at",sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(["owner_id"],["users.id"],ondelete="CASCADE"),sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_water_entries_owner_id","water_entries",["owner_id"])
def downgrade():
    op.drop_index("ix_water_entries_owner_id",table_name="water_entries")
    op.drop_table("water_entries")
    op.drop_index("ix_meals_owner_id",table_name="meals")
    op.drop_table("meals")
    op.drop_index("ix_foods_name",table_name="foods")
    op.drop_index("ix_foods_owner_id",table_name="foods")
    op.drop_table("foods")
    op.drop_index("ix_users_email",table_name="users")
    op.drop_table("users")
