"""Record new activity timestamps without inventing dates for existing data."""

import sqlalchemy as sa
from alembic import op

revision = "f2a_history_times"
down_revision = "b9055da31d3d"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("conversations", "turns"):
        op.add_column(table, sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        op.alter_column(table, "created_at", server_default=sa.func.now())
    op.add_column("turns", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("turns", "updated_at", server_default=sa.func.now())


def downgrade():
    op.drop_column("turns", "updated_at")
    for table in ("turns", "conversations"):
        op.drop_column(table, "created_at")
