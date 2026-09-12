"""Add internal state and relationship snapshots with evidence events."""

import sqlalchemy as sa
from alembic import op

revision = "f2d_state_boundary"
down_revision = "f2c_context_revision"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "character_instances",
        sa.Column("dynamics_revision", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "character_states",
        sa.Column("instance_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_turn_id", sa.String(length=36), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["instance_id"], ["character_instances.id"]),
        sa.ForeignKeyConstraint(["source_turn_id"], ["turns.id"]),
        sa.PrimaryKeyConstraint("instance_id"),
    )
    op.create_table(
        "relationships",
        sa.Column("instance_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("familiarity", sa.Text(), nullable=True),
        sa.Column("trust", sa.Text(), nullable=True),
        sa.Column("closeness", sa.Text(), nullable=True),
        sa.Column("source_turn_id", sa.String(length=36), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["instance_id"], ["character_instances.id"]),
        sa.ForeignKeyConstraint(["source_turn_id"], ["turns.id"]),
        sa.PrimaryKeyConstraint("instance_id"),
    )
    op.create_table(
        "state_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("instance_id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("source_turn_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("short_term_state", sa.Text(), nullable=True),
        sa.Column("familiarity", sa.Text(), nullable=True),
        sa.Column("trust", sa.Text(), nullable=True),
        sa.Column("closeness", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("excluded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'excluded')"),
        sa.ForeignKeyConstraint(["instance_id"], ["character_instances.id"]),
        sa.ForeignKeyConstraint(["source_turn_id"], ["turns.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instance_id", "request_id"),
        sa.UniqueConstraint("instance_id", "source_turn_id"),
    )
    op.create_index(
        op.f("ix_state_events_instance_id"),
        "state_events",
        ["instance_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_state_events_instance_id"), table_name="state_events")
    op.drop_table("state_events")
    op.drop_table("relationships")
    op.drop_table("character_states")
    op.drop_column("character_instances", "dynamics_revision")
