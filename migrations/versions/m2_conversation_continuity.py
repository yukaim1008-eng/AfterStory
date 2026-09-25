"""Add bounded conversation summaries and continuity notes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "m2_conversation_continuity"
down_revision = "m1_memory_foundations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "conversation_segments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("character_instances.id"), nullable=False
        ),
        sa.Column(
            "conversation_id", sa.String(36), sa.ForeignKey("conversations.id"), nullable=False
        ),
        sa.Column("start_sequence", sa.Integer(), nullable=False),
        sa.Column("end_sequence", sa.Integer(), nullable=False),
        sa.Column("turn_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("conversation_id", "start_sequence", "end_sequence"),
    )
    op.create_index(
        "ix_conversation_segments_instance_id", "conversation_segments", ["instance_id"]
    )
    op.create_index(
        "ix_conversation_segments_conversation_id", "conversation_segments", ["conversation_id"]
    )
    op.create_table(
        "segment_summaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "segment_id", sa.String(36), sa.ForeignKey("conversation_segments.id"), nullable=False
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("generator_version", sa.String(32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("segment_id", "revision"),
    )
    op.create_index("ix_segment_summaries_segment_id", "segment_summaries", ["segment_id"])
    op.create_table(
        "continuity_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("character_instances.id"), nullable=False
        ),
        sa.Column("topic_key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("current_progress", sa.Text(), nullable=False),
        sa.Column("open_question", sa.Text()),
        sa.Column("mention_policy", sa.String(24), nullable=False),
        sa.Column("last_turn_id", sa.String(36), sa.ForeignKey("turns.id")),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("instance_id", "topic_key"),
    )
    op.create_index("ix_continuity_notes_instance_id", "continuity_notes", ["instance_id"])


def downgrade():
    op.drop_table("continuity_notes")
    op.drop_table("segment_summaries")
    op.drop_table("conversation_segments")
