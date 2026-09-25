from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)


class Character(Base):
    __tablename__ = "characters"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))


class CharacterVersion(Base):
    __tablename__ = "character_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    character_id: Mapped[str] = mapped_column(ForeignKey("characters.id"))
    checkpoint: Mapped[str] = mapped_column(String(120))
    definition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text)


class CharacterInstance(Base):
    __tablename__ = "character_instances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("character_versions.id"))
    context_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    data_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    history_floor_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    dynamics_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instance_id: Mapped[str] = mapped_column(ForeignKey("character_instances.id"), index=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (
        UniqueConstraint("conversation_id", "request_id"),
        UniqueConstraint("conversation_id", "sequence"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(100))
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    attempt: Mapped[str] = mapped_column(String(36))
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    context_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("turn_id", "role"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    turn_id: Mapped[str] = mapped_column(ForeignKey("turns.id"), index=True)
    role: Mapped[str] = mapped_column(String(12))
    text: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    timezone_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timezone_source: Mapped[str | None] = mapped_column(String(24), nullable=True)


class PersonalMemory(Base):
    __tablename__ = "personal_memories"
    __table_args__ = (
        UniqueConstraint("instance_id", "create_request_id"),
        UniqueConstraint("instance_id", "source_message_id"),
        CheckConstraint("kind IN ('fact', 'inference')"),
        CheckConstraint("status IN ('active', 'deleted')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instance_id: Mapped[str] = mapped_column(ForeignKey("character_instances.id"), index=True)
    create_request_id: Mapped[str] = mapped_column(String(100))
    original_content_hash: Mapped[str] = mapped_column(String(64))
    source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20), default="fact")
    memory_type: Mapped[str] = mapped_column(String(20), default="fact", server_default="fact")
    memory_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PersonalMemoryVersion(Base):
    __tablename__ = "personal_memory_versions"
    __table_args__ = (UniqueConstraint("memory_id", "revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    memory_id: Mapped[str] = mapped_column(ForeignKey("personal_memories.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    memory_type: Mapped[str] = mapped_column(String(20))
    evidence_kind: Mapped[str] = mapped_column(String(24))
    payload: Mapped[dict] = mapped_column(JSONB)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    operation: Mapped[str] = mapped_column(String(20))
    previous_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("personal_memory_versions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MemorySourceLink(Base):
    __tablename__ = "memory_source_links"
    __table_args__ = (UniqueConstraint("memory_version_id", "source_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    memory_version_id: Mapped[str] = mapped_column(
        ForeignKey("personal_memory_versions.id"), index=True
    )
    source_key: Mapped[str] = mapped_column(String(120))
    source_kind: Mapped[str] = mapped_column(String(24))
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    turn_id: Mapped[str | None] = mapped_column(ForeignKey("turns.id"), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True
    )
    role: Mapped[str | None] = mapped_column(String(12), nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MemoryDependency(Base):
    __tablename__ = "memory_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "instance_id", "dependent_type", "dependent_id", "source_type", "source_id"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instance_id: Mapped[str] = mapped_column(ForeignKey("character_instances.id"), index=True)
    dependent_type: Mapped[str] = mapped_column(String(32))
    dependent_id: Mapped[str] = mapped_column(String(64))
    source_type: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(64))
    source_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MemorySuppression(Base):
    __tablename__ = "memory_suppressions"
    __table_args__ = (UniqueConstraint("instance_id", "request_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instance_id: Mapped[str] = mapped_column(ForeignKey("character_instances.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str] = mapped_column(String(24))
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MemoryJob(Base):
    __tablename__ = "memory_jobs"
    __table_args__ = (UniqueConstraint("instance_id", "job_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instance_id: Mapped[str] = mapped_column(ForeignKey("character_instances.id"), index=True)
    job_key: Mapped[str] = mapped_column(String(160))
    job_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    payload: Mapped[dict] = mapped_column(JSONB)
    target_data_revision: Mapped[int] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConversationSegment(Base):
    __tablename__ = "conversation_segments"
    __table_args__ = (UniqueConstraint("conversation_id", "start_sequence", "end_sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instance_id: Mapped[str] = mapped_column(ForeignKey("character_instances.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    start_sequence: Mapped[int] = mapped_column(Integer)
    end_sequence: Mapped[int] = mapped_column(Integer)
    turn_ids: Mapped[list] = mapped_column(JSONB)
    source_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SegmentSummary(Base):
    __tablename__ = "segment_summaries"
    __table_args__ = (UniqueConstraint("segment_id", "revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    segment_id: Mapped[str] = mapped_column(ForeignKey("conversation_segments.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    generator_version: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSONB)
    text: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ContinuityNote(Base):
    __tablename__ = "continuity_notes"
    __table_args__ = (UniqueConstraint("instance_id", "topic_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instance_id: Mapped[str] = mapped_column(ForeignKey("character_instances.id"), index=True)
    topic_key: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="open")
    current_progress: Mapped[str] = mapped_column(Text)
    open_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    mention_policy: Mapped[str] = mapped_column(String(24), default="when_relevant")
    last_turn_id: Mapped[str | None] = mapped_column(ForeignKey("turns.id"), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MemoryOperationReceipt(Base):
    __tablename__ = "memory_operation_receipts"
    __table_args__ = (UniqueConstraint("instance_id", "operation_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instance_id: Mapped[str] = mapped_column(ForeignKey("character_instances.id"), index=True)
    operation_id: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    target_memory_id: Mapped[str | None] = mapped_column(
        ForeignKey("personal_memories.id"), nullable=True
    )
    result_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MemoryIndexDocument(Base):
    __tablename__ = "memory_index_documents"
    __table_args__ = (UniqueConstraint("memory_id", "memory_revision"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instance_id: Mapped[str] = mapped_column(ForeignKey("character_instances.id"), index=True)
    memory_id: Mapped[str] = mapped_column(ForeignKey("personal_memories.id"), index=True)
    memory_revision: Mapped[int] = mapped_column(Integer)
    document_type: Mapped[str] = mapped_column(String(20), default="memory")
    content: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[object | None] = mapped_column(TSVECTOR, nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CharacterState(Base):
    __tablename__ = "character_states"
    instance_id: Mapped[str] = mapped_column(
        ForeignKey("character_instances.id"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_turn_id: Mapped[str | None] = mapped_column(ForeignKey("turns.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Relationship(Base):
    __tablename__ = "relationships"
    instance_id: Mapped[str] = mapped_column(
        ForeignKey("character_instances.id"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, default=0)
    familiarity: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust: Mapped[str | None] = mapped_column(Text, nullable=True)
    closeness: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_turn_id: Mapped[str | None] = mapped_column(ForeignKey("turns.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StateEvent(Base):
    __tablename__ = "state_events"
    __table_args__ = (
        UniqueConstraint("instance_id", "request_id"),
        UniqueConstraint("instance_id", "source_turn_id"),
        CheckConstraint("status IN ('active', 'excluded')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instance_id: Mapped[str] = mapped_column(ForeignKey("character_instances.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))
    source_turn_id: Mapped[str] = mapped_column(ForeignKey("turns.id"))
    revision: Mapped[int] = mapped_column(Integer)
    short_term_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    familiarity: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust: Mapped[str | None] = mapped_column(Text, nullable=True)
    closeness: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    excluded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
