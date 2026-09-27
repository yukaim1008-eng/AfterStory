from sqlalchemy import func, select

from afterstory.conversation import ConversationService
from afterstory.lifecycle import MemoryLifecycleService
from afterstory.memory import MemoryService
from afterstory.memory_automation import MemoryAutomationService
from afterstory.models import MemoryDependency, MemoryJob, PersonalMemory
from afterstory.repository import Repository
from afterstory.retrieval import RetrievalService


def candidate(messages, action="create", target=None, value="喜欢无糖茶"):
    user = next(item for item in messages if item["role"] == "user")
    return {
        "action": action,
        "target_memory_id": target,
        "reason": "用户明确说明",
        "memory": {
            "schema_version": "1.0",
            "evidence": "user_explicit",
            "importance_reason": "长期偏好",
            "payload": {
                "kind": "preference",
                "subject": "用户",
                "attribute": "饮品偏好",
                "value": value,
                "conditions": "",
                "scope": "reality",
                "valid_time": {"precision": "unknown"},
            },
            "sources": [
                {
                    "message_id": user["message_id"],
                    "turn_id": user["turn_id"],
                    "conversation_id": user["conversation_id"],
                    "role": "user",
                    "quote": user["text"],
                }
            ],
        },
    }


def test_delete_barrier_is_immediate_and_dependency_cleanup_is_bounded(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    memory = MemoryService(sessions).create("alice", instance_id, "many", "需要删除的资料")
    with sessions.begin() as session:
        for index in range(150):
            session.add(
                MemoryDependency(
                    instance_id=instance_id,
                    dependent_type="derived_test",
                    dependent_id=f"derived-{index}",
                    source_type="memory",
                    source_id=memory["memory_id"],
                    source_revision=1,
                    status="active",
                )
            )
    MemoryService(sessions).delete("alice", memory["memory_id"], 1)
    assert RetrievalService(sessions).prepare(instance_id, "资料").memory_items == []
    with sessions() as session:
        active = session.scalar(
            select(func.count())
            .select_from(MemoryDependency)
            .where(
                MemoryDependency.source_id == memory["memory_id"],
                MemoryDependency.status == "active",
            )
        )
        job = session.scalar(select(MemoryJob).where(MemoryJob.job_type == "rebuild_dependencies"))
        assert 0 < active <= 51
        assert job
    with sessions.begin() as session:
        job = session.scalar(select(MemoryJob).where(MemoryJob.job_type == "rebuild_dependencies"))
        assert MemoryLifecycleService.rebuild_batch(session, job)
    with sessions() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(MemoryDependency)
                .where(
                    MemoryDependency.source_id == memory["memory_id"],
                    MemoryDependency.status == "active",
                )
            )
            == 0
        )


def test_deleted_fingerprint_is_suppressed_and_explicit_correction_versions(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    chat = ConversationService(repo, type("Reply", (), {"generate": lambda _, __: "好"})())
    first_turn = chat.send("alice", conversation_id, "first", "我喜欢无糖茶")

    class CreateProvider:
        def extract(self, messages, existing_memories=None):
            return [candidate(messages)]

    automation = MemoryAutomationService(sessions, CreateProvider())
    created = automation.process_turn(first_turn.turn_id)[0]
    MemoryService(sessions).delete("alice", created["memory_id"], 1)
    second_turn = chat.send("alice", conversation_id, "second", "我喜欢无糖茶")
    assert automation.process_turn(second_turn.turn_id)[0]["status"] == "suppressed"

    manual = MemoryService(sessions).create("alice", instance_id, "old", "用户喜欢咖啡")
    correction_turn = chat.send("alice", conversation_id, "correct", "更正，我喜欢红茶")

    class CorrectionProvider:
        def extract(self, messages, existing_memories=None):
            return [candidate(messages, "correct", manual["memory_id"], "喜欢红茶")]

    result = MemoryAutomationService(sessions, CorrectionProvider()).process_turn(
        correction_turn.turn_id
    )[0]
    assert result["status"] == "corrected"
    with sessions() as session:
        corrected = session.get(PersonalMemory, manual["memory_id"])
        assert corrected.revision == 2
        assert "红茶" in corrected.content
