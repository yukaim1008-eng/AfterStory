"""Track the instance context revision used by every turn."""

import sqlalchemy as sa
from alembic import op

revision = "f2c_context_revision"
down_revision = "f2b_personal_memory"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "turns",
        sa.Column("context_revision", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade():
    op.drop_column("turns", "context_revision")
