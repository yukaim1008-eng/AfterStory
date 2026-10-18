"""Add one-use registration invites without changing existing accounts."""

import sqlalchemy as sa
from alembic import op

revision = "a2_invite_registration"
down_revision = "a1_authentication"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "registration_invites",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "consumed_by_user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("registration_invites")
