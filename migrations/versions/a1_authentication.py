"""Add credentials and server-side sessions without changing existing user data."""

import sqlalchemy as sa
from alembic import op

revision = "a1_authentication"
down_revision = "m7_state_relationship"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("username", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column(
        "users", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False)
    )
    op.create_unique_constraint("uq_users_username", "users", ["username"])
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table(
        "auth_login_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope_hash", sa.String(64), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_auth_login_attempts_scope_hash", "auth_login_attempts", ["scope_hash"])
    op.create_index("ix_auth_login_attempts_occurred_at", "auth_login_attempts", ["occurred_at"])


def downgrade():
    op.drop_table("auth_login_attempts")
    op.drop_table("auth_sessions")
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "username")
