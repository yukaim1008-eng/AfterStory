"""Add rebuildable full-text and embedding index documents."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "m4_hybrid_retrieval"
down_revision = "m3_memory_extraction"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "memory_index_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("character_instances.id"), nullable=False
        ),
        sa.Column(
            "memory_id", sa.String(36), sa.ForeignKey("personal_memories.id"), nullable=False
        ),
        sa.Column("memory_revision", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR()),
        sa.Column("embedding", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("embedding_version", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("memory_id", "memory_revision"),
    )
    op.create_index(
        "ix_memory_index_documents_instance_id", "memory_index_documents", ["instance_id"]
    )
    op.create_index("ix_memory_index_documents_memory_id", "memory_index_documents", ["memory_id"])
    op.create_index(
        "ix_memory_index_documents_search_vector",
        "memory_index_documents",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.execute(
        sa.text("""
        INSERT INTO memory_index_documents
            (id, instance_id, memory_id, memory_revision, document_type, content,
             search_vector, status, created_at)
        SELECT gen_random_uuid()::text, instance_id, id, revision, 'memory', content,
               to_tsvector('simple', coalesce(content, '')), 'active', updated_at
        FROM personal_memories
        WHERE status = 'active' AND content IS NOT NULL
    """)
    )


def downgrade():
    op.drop_table("memory_index_documents")
