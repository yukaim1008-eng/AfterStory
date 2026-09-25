"""Add optional source spans for fine-grained lifecycle rebuilds."""

import sqlalchemy as sa
from alembic import op

revision = "m6_memory_lifecycle"
down_revision = "m5_matters_reminders"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("memory_source_links", sa.Column("span_start", sa.Integer()))
    op.add_column("memory_source_links", sa.Column("span_end", sa.Integer()))
    op.create_check_constraint(
        "ck_memory_source_span",
        "memory_source_links",
        "(span_start IS NULL AND span_end IS NULL) OR (span_start >= 0 AND span_end >= span_start)",
    )


def downgrade():
    op.drop_constraint("ck_memory_source_span", "memory_source_links", type_="check")
    op.drop_column("memory_source_links", "span_end")
    op.drop_column("memory_source_links", "span_start")
