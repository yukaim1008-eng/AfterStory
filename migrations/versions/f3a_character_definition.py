"""Add optional structured character definitions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f3a_character_definition"
down_revision = "f2d_state_boundary"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "character_versions",
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade():
    op.drop_column("character_versions", "definition")
