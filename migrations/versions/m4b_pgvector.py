"""Use the PostgreSQL vector extension for embedding storage."""

from alembic import op

revision = "m4b_pgvector"
down_revision = "m4_hybrid_retrieval"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
    op.execute(
        "ALTER TABLE memory_index_documents "
        "ALTER COLUMN embedding TYPE public.vector "
        "USING embedding::text::public.vector"
    )


def downgrade():
    op.execute(
        "ALTER TABLE memory_index_documents "
        "ALTER COLUMN embedding TYPE jsonb USING embedding::text::jsonb"
    )
