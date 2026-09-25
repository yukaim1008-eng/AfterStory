"""Add immutable memory foundations and message time provenance."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "m1_memory_foundations"
down_revision = "f3a_character_definition"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "character_instances",
        sa.Column("data_revision", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "messages",
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column("messages", sa.Column("timezone_name", sa.String(64)))
    op.add_column("messages", sa.Column("timezone_source", sa.String(24)))
    op.add_column(
        "personal_memories",
        sa.Column("memory_type", sa.String(20), server_default="fact", nullable=False),
    )

    op.create_table(
        "personal_memory_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "memory_id", sa.String(36), sa.ForeignKey("personal_memories.id"), nullable=False
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("memory_type", sa.String(20), nullable=False),
        sa.Column("evidence_kind", sa.String(24), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column(
            "previous_version_id", sa.String(36), sa.ForeignKey("personal_memory_versions.id")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("memory_id", "revision"),
    )
    op.create_index(
        "ix_personal_memory_versions_memory_id", "personal_memory_versions", ["memory_id"]
    )
    op.create_table(
        "memory_source_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "memory_version_id",
            sa.String(36),
            sa.ForeignKey("personal_memory_versions.id"),
            nullable=False,
        ),
        sa.Column("source_key", sa.String(120), nullable=False),
        sa.Column("source_kind", sa.String(24), nullable=False),
        sa.Column("message_id", sa.String(36), sa.ForeignKey("messages.id")),
        sa.Column("turn_id", sa.String(36), sa.ForeignKey("turns.id")),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id")),
        sa.Column("role", sa.String(12)),
        sa.Column("quote", sa.Text()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("memory_version_id", "source_key"),
    )
    op.create_index(
        "ix_memory_source_links_memory_version_id", "memory_source_links", ["memory_version_id"]
    )
    op.create_table(
        "memory_dependencies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("character_instances.id"), nullable=False
        ),
        sa.Column("dependent_type", sa.String(32), nullable=False),
        sa.Column("dependent_id", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("source_revision", sa.Integer()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "instance_id", "dependent_type", "dependent_id", "source_type", "source_id"
        ),
    )
    op.create_index("ix_memory_dependencies_instance_id", "memory_dependencies", ["instance_id"])
    op.create_table(
        "memory_suppressions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("character_instances.id"), nullable=False
        ),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(24), nullable=False),
        sa.Column("target_id", sa.String(64)),
        sa.Column("fingerprint", sa.String(64)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("instance_id", "request_id"),
    )
    op.create_index("ix_memory_suppressions_instance_id", "memory_suppressions", ["instance_id"])
    op.create_table(
        "memory_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("character_instances.id"), nullable=False
        ),
        sa.Column("job_key", sa.String(160), nullable=False),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("target_data_revision", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("instance_id", "job_key"),
    )
    op.create_index("ix_memory_jobs_instance_id", "memory_jobs", ["instance_id"])

    # Old rows become one explicit legacy version. No semantic fields are guessed.
    op.execute(
        sa.text("""
        INSERT INTO personal_memory_versions
            (id, memory_id, revision, schema_version, memory_type, evidence_kind,
             payload, content, status, operation, created_at)
        SELECT gen_random_uuid()::text, id, revision, '1.0', 'fact',
               CASE WHEN kind = 'inference' THEN 'inference' ELSE 'legacy' END,
               jsonb_build_object('content', content), content, status, 'import', created_at
        FROM personal_memories
    """)
    )
    op.execute(
        sa.text("""
        INSERT INTO memory_source_links
            (id, memory_version_id, source_key, source_kind, message_id, turn_id,
             conversation_id, role, quote, content_hash, created_at)
        SELECT gen_random_uuid()::text, v.id,
               CASE WHEN p.source_message_id IS NULL
                    THEN 'legacy:' || p.id
                    ELSE 'message:' || p.source_message_id
               END,
               CASE WHEN p.source_message_id IS NULL THEN 'manual' ELSE 'message' END,
               m.id, t.id, t.conversation_id, m.role, m.text,
               NULL,
               p.created_at
        FROM personal_memories p
        JOIN personal_memory_versions v ON v.memory_id = p.id AND v.revision = p.revision
        LEFT JOIN messages m ON m.id = p.source_message_id
        LEFT JOIN turns t ON t.id = m.turn_id
    """)
    )


def downgrade():
    op.drop_table("memory_jobs")
    op.drop_table("memory_suppressions")
    op.drop_table("memory_dependencies")
    op.drop_table("memory_source_links")
    op.drop_table("personal_memory_versions")
    op.drop_column("personal_memories", "memory_type")
    op.drop_column("messages", "timezone_source")
    op.drop_column("messages", "timezone_name")
    op.drop_column("messages", "recorded_at")
    op.drop_column("character_instances", "data_revision")
