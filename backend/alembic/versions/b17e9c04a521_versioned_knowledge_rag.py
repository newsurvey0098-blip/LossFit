"""Store versioned nutrition sources, retrievable chunks and assistant citations."""
from alembic import op
import sqlalchemy as sa

revision = "b17e9c04a521"
down_revision = "41c6a2d8e903"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("organization", sa.String(length=180), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", "version", name="uq_knowledge_source_version"),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "chunk_index", name="uq_knowledge_chunk_source_index"),
    )
    op.create_index(op.f("ix_knowledge_chunks_source_id"), "knowledge_chunks", ["source_id"], unique=False)
    op.add_column("assistant_messages", sa.Column("citations", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("assistant_messages", "citations")
    op.drop_index(op.f("ix_knowledge_chunks_source_id"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_sources")
