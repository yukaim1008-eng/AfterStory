import json
from hashlib import sha256

from sqlalchemy import select

from afterstory.domain import DomainError
from afterstory.lifecycle import MemoryLifecycleService
from afterstory.memory import MemoryService
from afterstory.memory_contracts import MemoryOperationCandidate
from afterstory.models import (
    CharacterInstance,
    Conversation,
    MemoryOperationReceipt,
    MemorySuppression,
    Message,
    PersonalMemory,
    Turn,
)


def memory_key(payload):
    value = payload.model_dump(mode="json")
    # The stable key identifies the subject/attribute or event identity, while the
    # full payload remains versioned content.
    if payload.kind in {"fact", "preference"}:
        identity = {
            "kind": payload.kind,
            "subject": payload.subject.casefold(),
            "attribute": payload.attribute.casefold(),
            "scope": payload.scope,
        }
    else:
        identity = {
            "kind": "event",
            "title": payload.title.casefold(),
            "scene": payload.scene,
            "occurred_at": value["occurred_at"],
        }
    return sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def memory_content(payload):
    if payload.kind in {"fact", "preference"}:
        suffix = f"（{payload.conditions}）" if payload.conditions else ""
        return f"{payload.subject}的{payload.attribute}：{payload.value}{suffix}"
    return f"{payload.title}：{payload.summary}"


class MemoryAutomationService:
    """Commits validated extraction candidates without invalidating in-flight replies."""

    def __init__(self, sessions, provider):
        self.sessions = sessions
        self.provider = provider

    def process_turn(self, turn_id):
        with self.sessions() as session:
            turn = session.get(Turn, turn_id)
            if not turn or turn.status != "completed":
                raise DomainError(404, "completed_turn_not_found")
            conversation = session.get(Conversation, turn.conversation_id)
            messages = list(session.scalars(select(Message).where(Message.turn_id == turn_id)))
            provider_input = [
                {
                    "message_id": item.id,
                    "turn_id": turn.id,
                    "conversation_id": conversation.id,
                    "role": item.role,
                    "text": item.text,
                }
                for item in messages
            ]
            allowed_sources = {item["message_id"] for item in provider_input}
            instance_id = conversation.instance_id

        candidates = [
            MemoryOperationCandidate.model_validate(item)
            for item in self.provider.extract(provider_input)
        ]
        results = []
        for index, operation in enumerate(candidates):
            if operation.action in {"no_change", "defer"} or operation.memory is None:
                results.append({"index": index, "status": operation.action})
                continue
            if any(source.message_id not in allowed_sources for source in operation.memory.sources):
                raise ValueError("memory_source_outside_extraction_input")
            if operation.action == "correct":
                if operation.memory.evidence != "user_explicit":
                    results.append(
                        {"index": index, "status": "deferred_requires_explicit_confirmation"}
                    )
                else:
                    results.append(self._correct(instance_id, index, operation))
                continue
            results.append(self._commit(instance_id, turn_id, index, operation))
        return results

    def _commit(self, instance_id, turn_id, index, operation):
        candidate = operation.memory
        key = memory_key(candidate.payload)
        content = memory_content(candidate.payload)
        with self.sessions.begin() as session:
            instance = session.scalar(
                select(CharacterInstance)
                .where(CharacterInstance.id == instance_id)
                .with_for_update()
            )
            existing = session.scalar(
                select(PersonalMemory).where(
                    PersonalMemory.instance_id == instance_id,
                    PersonalMemory.memory_key == key,
                    PersonalMemory.status == "active",
                )
            )
            if existing:
                return {"index": index, "status": "deduplicated", "memory_id": existing.id}
            if session.scalar(
                select(MemorySuppression).where(
                    MemorySuppression.instance_id == instance_id,
                    MemorySuppression.fingerprint == key,
                    MemorySuppression.status == "active",
                )
            ):
                return {"index": index, "status": "suppressed"}
            request_id = f"auto:{turn_id}:{index}"
            memory = session.scalar(
                select(PersonalMemory).where(
                    PersonalMemory.instance_id == instance_id,
                    PersonalMemory.create_request_id == request_id,
                )
            )
            if memory:
                return {"index": index, "status": "idempotent", "memory_id": memory.id}
            memory = PersonalMemory(
                instance_id=instance_id,
                create_request_id=request_id,
                original_content_hash=sha256(content.encode()).hexdigest(),
                kind="inference" if candidate.evidence == "inference" else "fact",
                memory_type=candidate.payload.kind,
                memory_key=key,
                content=content,
                status="active",
                revision=1,
            )
            session.add(memory)
            instance.data_revision += 1
            session.flush()
            source = candidate.sources[0]
            row = session.execute(
                select(Message, Turn, Conversation)
                .join(Turn, Turn.id == Message.turn_id)
                .join(Conversation, Conversation.id == Turn.conversation_id)
                .where(Message.id == source.message_id)
            ).first()
            MemoryService._append_version(
                session,
                memory,
                "create",
                evidence_kind=candidate.evidence,
                source=row,
            )
            MemoryService._sync_index(session, memory)
            return {"index": index, "status": "created", "memory_id": memory.id}

    def _correct(self, instance_id, index, operation):
        if not operation.target_memory_id:
            return {"index": index, "status": "deferred_missing_target"}
        candidate = operation.memory
        content = memory_content(candidate.payload)
        with self.sessions.begin() as session:
            instance = session.scalar(
                select(CharacterInstance)
                .where(CharacterInstance.id == instance_id)
                .with_for_update()
            )
            memory = session.scalar(
                select(PersonalMemory)
                .where(
                    PersonalMemory.id == operation.target_memory_id,
                    PersonalMemory.instance_id == instance_id,
                    PersonalMemory.status == "active",
                )
                .with_for_update()
            )
            if not memory:
                return {"index": index, "status": "deferred_target_unavailable"}
            memory.content = content
            memory.memory_type = candidate.payload.kind
            memory.memory_key = memory_key(candidate.payload)
            memory.kind = "fact"
            memory.revision += 1
            instance.data_revision += 1
            instance.context_revision += 1
            instance.history_floor_revision = instance.context_revision
            session.flush()
            source = candidate.sources[0]
            row = session.execute(
                select(Message, Turn, Conversation)
                .join(Turn, Turn.id == Message.turn_id)
                .join(Conversation, Conversation.id == Turn.conversation_id)
                .where(Message.id == source.message_id)
            ).first()
            MemoryService._append_version(
                session,
                memory,
                "correct",
                evidence_kind=candidate.evidence,
                source=row,
            )
            MemoryService._sync_index(session, memory)
            MemoryLifecycleService.invalidate_dependents(session, instance, memory)
            return {
                "index": index,
                "status": "corrected",
                "memory_id": memory.id,
                "revision": memory.revision,
            }


class ExplicitMemoryOperationService:
    def __init__(self, sessions):
        self.sessions = sessions
        self.memories = MemoryService(sessions)

    def execute(
        self,
        user,
        instance_id,
        operation_id,
        action,
        content=None,
        memory_id=None,
        expected_revision=None,
    ):
        with self.sessions() as session:
            existing = session.scalar(
                select(MemoryOperationReceipt).where(
                    MemoryOperationReceipt.instance_id == instance_id,
                    MemoryOperationReceipt.operation_id == operation_id,
                )
            )
            if existing:
                return self._view(existing)
            if action in {"correct", "forget"}:
                memory, _ = MemoryService._owned_memory(session, user, memory_id)
                if memory.instance_id != instance_id:
                    raise DomainError(404, "memory_not_found")
        if action == "remember":
            result = self.memories.create(user, instance_id, operation_id, content)
        elif action == "correct":
            result = self.memories.update(user, memory_id, expected_revision, content)
        elif action == "forget":
            result = self.memories.delete(user, memory_id, expected_revision)
        else:
            raise DomainError(422, "unsupported_memory_operation")
        with self.sessions.begin() as session:
            receipt = MemoryOperationReceipt(
                instance_id=instance_id,
                operation_id=operation_id,
                action=action,
                status="committed",
                target_memory_id=result["memory_id"],
                result_revision=result["revision"],
            )
            session.add(receipt)
            session.flush()
            return self._view(receipt)

    @staticmethod
    def _view(receipt):
        return {
            "operation_id": receipt.operation_id,
            "action": receipt.action,
            "status": receipt.status,
            "memory_id": receipt.target_memory_id,
            "revision": receipt.result_revision,
            "error_code": receipt.error_code,
        }
