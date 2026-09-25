"""Add ongoing matters and single in-app reminder delivery."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "m5_matters_reminders"
down_revision = "m4b_pgvector"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ongoing_matters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("character_instances.id"), nullable=False
        ),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("matter_type", sa.String(24), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("next_step", sa.Text()),
        sa.Column("time_precision", sa.String(20), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("timezone_name", sa.String(64)),
        sa.Column("mention_policy", sa.String(24), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("instance_id", "request_id"),
    )
    op.create_index("ix_ongoing_matters_instance_id", "ongoing_matters", ["instance_id"])
    op.create_table(
        "matter_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("matter_id", sa.String(36), sa.ForeignKey("ongoing_matters.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("matter_id", "revision"),
    )
    op.create_index("ix_matter_revisions_matter_id", "matter_revisions", ["matter_id"])
    op.create_table(
        "reminders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("character_instances.id"), nullable=False
        ),
        sa.Column("matter_id", sa.String(36), sa.ForeignKey("ongoing_matters.id"), nullable=False),
        sa.Column("schedule_revision", sa.Integer(), nullable=False),
        sa.Column("occurrence_key", sa.String(120), nullable=False, unique=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("matter_id", "schedule_revision"),
    )
    op.create_index("ix_reminders_instance_id", "reminders", ["instance_id"])
    op.create_index("ix_reminders_matter_id", "reminders", ["matter_id"])
    op.create_index("ix_reminders_due_at", "reminders", ["due_at"])
    op.create_table(
        "reminder_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reminder_id", sa.String(36), sa.ForeignKey("reminders.id"), nullable=False),
        sa.Column("occurrence_key", sa.String(120), nullable=False),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("reminder_id", "channel"),
    )
    op.create_index("ix_reminder_deliveries_reminder_id", "reminder_deliveries", ["reminder_id"])


def downgrade():
    op.drop_table("reminder_deliveries")
    op.drop_table("reminders")
    op.drop_table("matter_revisions")
    op.drop_table("ongoing_matters")
