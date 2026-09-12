"""Add instance-scoped manually managed personal memories."""

import sqlalchemy as sa
from alembic import op

revision = "f2b_personal_memory"
down_revision = "f2a_history_times"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "character_instances",
        sa.Column("context_revision", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "character_instances",
        sa.Column("history_floor_revision", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "personal_memories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("instance_id", sa.String(length=36), nullable=False),
        sa.Column("create_request_id", sa.String(length=100), nullable=False),
        sa.Column("original_content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_message_id", sa.String(length=36), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('fact', 'inference')"),
        sa.CheckConstraint("status IN ('active', 'deleted')"),
        sa.ForeignKeyConstraint(["instance_id"], ["character_instances.id"]),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instance_id", "create_request_id"),
        sa.UniqueConstraint("instance_id", "source_message_id"),
    )
    op.create_index(
        op.f("ix_personal_memories_instance_id"),
        "personal_memories",
        ["instance_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_personal_memories_instance_id"), table_name="personal_memories")
    op.drop_table("personal_memories")
    op.drop_column("character_instances", "history_floor_revision")
    op.drop_column("character_instances", "context_revision")
