from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy import func, select

from afterstory.domain import DomainError
from afterstory.lifecycle import MemoryLifecycleService
from afterstory.models import (
    CharacterInstance,
    Conversation,
    MemoryDependency,
    MemoryIndexDocument,
    MemorySourceLink,
    MemorySuppression,
    Message,
    PersonalMemory,
    PersonalMemoryVersion,
    Turn,
)
from afterstory.state import StateService


class MemoryService:
    def __init__(self, sessions):
        self.sessions = sessions

    @staticmethod
    def _sync_index(session, memory):
        for document in session.scalars(
            select(MemoryIndexDocument).where(
                MemoryIndexDocument.memory_id == memory.id,
                MemoryIndexDocument.status == "active",
            )
        ):
            document.status = "stale"
        if memory.status != "active" or not memory.content:
            return
        existing = session.scalar(
            select(MemoryIndexDocument).where(
                MemoryIndexDocument.memory_id == memory.id,
                MemoryIndexDocument.memory_revision == memory.revision,
            )
        )
        if existing:
            existing.status = "active"
            dependency = session.scalar(
                select(MemoryDependency).where(
                    MemoryDependency.instance_id == memory.instance_id,
                    MemoryDependency.dependent_type == "memory_index",
                    MemoryDependency.dependent_id == existing.id,
                    MemoryDependency.source_type == "memory",
                    MemoryDependency.source_id == memory.id,
                )
            )
            if not dependency:
                session.add(
                    MemoryDependency(
                        instance_id=memory.instance_id,
                        dependent_type="memory_index",
                        dependent_id=existing.id,
                        source_type="memory",
                        source_id=memory.id,
                        source_revision=memory.revision,
                        status="active",
                    )
                )
            return
        document = MemoryIndexDocument(
            instance_id=memory.instance_id,
            memory_id=memory.id,
            memory_revision=memory.revision,
            document_type="memory",
            content=memory.content,
            search_vector=func.to_tsvector("simple", memory.content),
            status="active",
        )
        session.add(document)
        session.flush()
        session.add(
            MemoryDependency(
                instance_id=memory.instance_id,
                dependent_type="memory_index",
                dependent_id=document.id,
                source_type="memory",
                source_id=memory.id,
                source_revision=memory.revision,
                status="active",
            )
        )

    @staticmethod
    def _append_version(
        session,
        memory,
        operation,
        evidence_kind="manual",
        source=None,
        structured_payload=None,
    ):
        previous = session.scalar(
            select(PersonalMemoryVersion)
            .where(PersonalMemoryVersion.memory_id == memory.id)
            .order_by(PersonalMemoryVersion.revision.desc())
            .limit(1)
        )
        version = PersonalMemoryVersion(
            memory_id=memory.id,
            revision=memory.revision,
            schema_version="1.0",
            memory_type=memory.memory_type,
            evidence_kind=evidence_kind,
            payload=structured_payload or {"content": memory.content},
            content=memory.content,
            status=memory.status,
            operation=operation,
            previous_version_id=previous.id if previous else None,
        )
        session.add(version)
        session.flush()
        if source:
            message, turn, conversation = source
            session.add(
                MemorySourceLink(
                    memory_version_id=version.id,
                    source_key=f"message:{message.id}",
                    source_kind="message",
                    message_id=message.id,
                    turn_id=turn.id,
                    conversation_id=conversation.id,
                    role=message.role,
                    quote=message.text,
                    content_hash=sha256(message.text.encode()).hexdigest(),
                )
            )
        else:
            session.add(
                MemorySourceLink(
                    memory_version_id=version.id,
                    source_key=f"manual:{memory.create_request_id}:{memory.revision}",
                    source_kind="manual",
                )
            )
        return version

    @staticmethod
    def _owned_instance(session, user, instance_id, lock=False):
        query = select(CharacterInstance).where(
            CharacterInstance.id == instance_id, CharacterInstance.user_id == user
        )
        if lock:
            query = query.with_for_update()
        instance = session.scalar(query)
        if not instance:
            raise DomainError(404, "instance_not_found")
        return instance

    @staticmethod
    def _owned_memory(session, user, memory_id, lock_instance=False):
        instance_query = (
            select(CharacterInstance)
            .join(PersonalMemory, PersonalMemory.instance_id == CharacterInstance.id)
            .where(PersonalMemory.id == memory_id, CharacterInstance.user_id == user)
        )
        if lock_instance:
            instance_query = instance_query.with_for_update(of=CharacterInstance)
        instance = session.scalar(instance_query)
        if not instance:
            raise DomainError(404, "memory_not_found")
        memory = session.get(PersonalMemory, memory_id)
        return memory, instance

    @staticmethod
    def _source(session, instance_id, message_id):
        row = session.execute(
            select(Message, Turn, Conversation)
            .join(Turn, Turn.id == Message.turn_id)
            .join(Conversation, Conversation.id == Turn.conversation_id)
            .where(
                Message.id == message_id,
                Conversation.instance_id == instance_id,
                Turn.status == "completed",
                Message.role == "user",
            )
        ).first()
        if not row:
            raise DomainError(404, "memory_source_not_found")
        return row

    @staticmethod
    def _view(session, memory):
        source = None
        if memory.source_message_id:
            row = session.execute(
                select(Message, Turn, Conversation)
                .join(Turn, Turn.id == Message.turn_id)
                .join(Conversation, Conversation.id == Turn.conversation_id)
                .where(Message.id == memory.source_message_id)
            ).first()
            if row:
                message, turn, conversation = row
                source = dict(
                    message_id=message.id,
                    turn_id=turn.id,
                    conversation_id=conversation.id,
                    role=message.role,
                )
        return dict(
            memory_id=memory.id,
            instance_id=memory.instance_id,
            kind=memory.kind,
            memory_type=memory.memory_type,
            content=memory.content,
            status=memory.status,
            revision=memory.revision,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            source=source,
        )

    def list(self, user, instance_id, offset=0, limit=50):
        with self.sessions() as session:
            self._owned_instance(session, user, instance_id)
            condition = (
                PersonalMemory.instance_id == instance_id,
                PersonalMemory.status == "active",
            )
            total = session.scalar(
                select(func.count()).select_from(PersonalMemory).where(*condition)
            )
            memories = list(
                session.scalars(
                    select(PersonalMemory)
                    .where(*condition)
                    .order_by(PersonalMemory.updated_at.desc(), PersonalMemory.id)
                    .offset(offset)
                    .limit(limit)
                )
            )
            return dict(
                items=[self._view(session, memory) for memory in memories],
                total=total,
                offset=offset,
                limit=limit,
            )

    def create(self, user, instance_id, request_id, content, source_message_id=None):
        digest = sha256(content.encode()).hexdigest()
        with self.sessions.begin() as session:
            instance = self._owned_instance(session, user, instance_id, lock=True)
            existing = session.scalar(
                select(PersonalMemory).where(
                    PersonalMemory.instance_id == instance_id,
                    PersonalMemory.create_request_id == request_id,
                )
            )
            if existing:
                if (
                    existing.original_content_hash != digest
                    or existing.source_message_id != source_message_id
                ):
                    raise DomainError(409, "memory_request_conflict")
                if existing.status == "deleted":
                    raise DomainError(409, "memory_deleted")
                return self._view(session, existing)
            source = None
            if source_message_id:
                source = self._source(session, instance_id, source_message_id)
                if session.scalar(
                    select(PersonalMemory).where(
                        PersonalMemory.instance_id == instance_id,
                        PersonalMemory.source_message_id == source_message_id,
                    )
                ):
                    raise DomainError(409, "memory_source_already_saved")
            memory = PersonalMemory(
                instance_id=instance_id,
                create_request_id=request_id,
                original_content_hash=digest,
                source_message_id=source_message_id,
                kind="fact",
                memory_type="fact",
                content=content,
                status="active",
                revision=1,
            )
            session.add(memory)
            instance.data_revision += 1
            instance.context_revision += 1
            session.flush()
            self._append_version(session, memory, "create", source=source)
            self._sync_index(session, memory)
            return self._view(session, memory)

    def update(self, user, memory_id, expected_revision, content, source_message_id=None):
        with self.sessions.begin() as session:
            memory, instance = self._owned_memory(session, user, memory_id, lock_instance=True)
            if memory.status == "deleted":
                raise DomainError(409, "memory_deleted")
            if memory.revision != expected_revision:
                raise DomainError(409, "memory_revision_conflict")
            instance.context_revision += 1
            instance.data_revision += 1
            instance.history_floor_revision = instance.context_revision
            StateService.invalidate_for_memory_change(session, instance)
            memory.content = content
            memory.revision += 1
            memory.updated_at = datetime.now(timezone.utc)
            session.flush()
            source = (
                self._source(session, memory.instance_id, source_message_id)
                if source_message_id
                else None
            )
            self._append_version(session, memory, "update", source=source)
            self._sync_index(session, memory)
            MemoryLifecycleService.invalidate_dependents(session, instance, memory)
            return self._view(session, memory)

    def delete(self, user, memory_id, expected_revision, source_message_id=None):
        with self.sessions.begin() as session:
            memory, instance = self._owned_memory(session, user, memory_id, lock_instance=True)
            if memory.status == "deleted":
                if memory.revision == expected_revision + 1:
                    return self._view(session, memory)
                raise DomainError(409, "memory_deleted")
            if memory.revision != expected_revision:
                raise DomainError(409, "memory_revision_conflict")
            now = datetime.now(timezone.utc)
            instance.context_revision += 1
            instance.data_revision += 1
            instance.history_floor_revision = instance.context_revision
            StateService.invalidate_for_memory_change(session, instance, now)
            memory.content = None
            memory.status = "deleted"
            memory.revision += 1
            memory.updated_at = now
            memory.deleted_at = now
            session.flush()
            source = (
                self._source(session, memory.instance_id, source_message_id)
                if source_message_id
                else None
            )
            self._append_version(session, memory, "delete", source=source)
            self._sync_index(session, memory)
            if memory.memory_key:
                session.add(
                    MemorySuppression(
                        instance_id=memory.instance_id,
                        request_id=f"delete:{memory.id}:{memory.revision}",
                        target_type="fingerprint",
                        target_id=memory.id,
                        fingerprint=memory.memory_key,
                        status="active",
                    )
                )
            MemoryLifecycleService.invalidate_dependents(session, instance, memory)
            return self._view(session, memory)
