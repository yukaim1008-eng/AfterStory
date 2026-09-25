"""Separate state duration from slow relationship evidence and revisions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "m7_state_relationship"
down_revision = "m6_memory_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "character_states",
        sa.Column("persistence", sa.String(20), server_default="transient", nullable=False),
    )
    op.add_column("character_states", sa.Column("valid_until", sa.DateTime(timezone=True)))
    op.add_column(
        "state_events",
        sa.Column("persistence", sa.String(20), server_default="transient", nullable=False),
    )
    op.add_column("state_events", sa.Column("valid_until", sa.DateTime(timezone=True)))
    op.create_table(
        "relationship_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("character_instances.id"), nullable=False
        ),
        sa.Column("source_turn_id", sa.String(36), sa.ForeignKey("turns.id"), nullable=False),
        sa.Column("aspect", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("instance_id", "source_turn_id", "aspect"),
    )
    op.create_index(
        "ix_relationship_evidence_instance_id", "relationship_evidence", ["instance_id"]
    )
    op.create_table(
        "relationship_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("character_instances.id"), nullable=False
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("familiarity", sa.Text()),
        sa.Column("trust", sa.Text()),
        sa.Column("closeness", sa.Text()),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("instance_id", "revision"),
    )
    op.create_index(
        "ix_relationship_revisions_instance_id", "relationship_revisions", ["instance_id"]
    )


def downgrade():
    op.drop_table("relationship_revisions")
    op.drop_table("relationship_evidence")
    op.drop_column("state_events", "valid_until")
    op.drop_column("state_events", "persistence")
    op.drop_column("character_states", "valid_until")
    op.drop_column("character_states", "persistence")
