from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy import func, select

from afterstory.domain import DomainError
from afterstory.models import CharacterInstance, Conversation, Message, PersonalMemory, Turn


class MemoryService:
    def __init__(self, sessions):
        self.sessions = sessions

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
            if source_message_id:
                self._source(session, instance_id, source_message_id)
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
                content=content,
                status="active",
                revision=1,
            )
            session.add(memory)
            instance.context_revision += 1
            session.flush()
            return self._view(session, memory)

    def update(self, user, memory_id, expected_revision, content):
        with self.sessions.begin() as session:
            memory, instance = self._owned_memory(session, user, memory_id, lock_instance=True)
            if memory.status == "deleted":
                raise DomainError(409, "memory_deleted")
            if memory.revision != expected_revision:
                raise DomainError(409, "memory_revision_conflict")
            instance.context_revision += 1
            instance.history_floor_revision = instance.context_revision
            memory.content = content
            memory.revision += 1
            memory.updated_at = datetime.now(timezone.utc)
            session.flush()
            return self._view(session, memory)

    def delete(self, user, memory_id, expected_revision):
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
            instance.history_floor_revision = instance.context_revision
            memory.content = None
            memory.status = "deleted"
            memory.revision += 1
            memory.updated_at = now
            memory.deleted_at = now
            session.flush()
            return self._view(session, memory)
