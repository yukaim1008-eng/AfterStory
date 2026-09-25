"""Add stable memory identity and explicit operation receipts."""

import sqlalchemy as sa
from alembic import op

revision = "m3_memory_extraction"
down_revision = "m2_conversation_continuity"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("personal_memories", sa.Column("memory_key", sa.String(64)))
    op.create_index("ix_personal_memories_memory_key", "personal_memories", ["memory_key"])
    op.create_table(
        "memory_operation_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("character_instances.id"), nullable=False
        ),
        sa.Column("operation_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("target_memory_id", sa.String(36), sa.ForeignKey("personal_memories.id")),
        sa.Column("result_revision", sa.Integer()),
        sa.Column("error_code", sa.String(80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("instance_id", "operation_id"),
    )
    op.create_index(
        "ix_memory_operation_receipts_instance_id", "memory_operation_receipts", ["instance_id"]
    )


def downgrade():
    op.drop_table("memory_operation_receipts")
    op.drop_column("personal_memories", "memory_key")
