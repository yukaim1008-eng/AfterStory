"""Use the PostgreSQL vector extension for embedding storage."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "m4b_pgvector"
down_revision = "m4_hybrid_retrieval"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.alter_column(
        "memory_index_documents",
        "embedding",
        existing_type=sa.JSON(),
        type_=Vector(),
        postgresql_using="embedding::text::vector",
    )


def downgrade():
    op.alter_column(
        "memory_index_documents",
        "embedding",
        existing_type=Vector(),
        type_=sa.JSON(),
        postgresql_using="embedding::text::jsonb",
    )
