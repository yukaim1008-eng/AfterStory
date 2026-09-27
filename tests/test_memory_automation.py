from datetime import datetime

from sqlalchemy import func, select

from afterstory.conversation import ConversationService
from afterstory.memory_automation import ExplicitMemoryOperationService, MemoryAutomationService
from afterstory.models import CharacterInstance, MemoryJob, PersonalMemory, PersonalMemoryVersion
from afterstory.repository import Repository


class ExtractionProvider:
    def extract(self, messages, existing_memories=None):
        user = next(item for item in messages if item["role"] == "user")
        return [
            {
                "action": "create",
                "target_memory_id": None,
                "reason": "用户明确表达稳定偏好",
                "memory": {
                    "schema_version": "1.0",
                    "evidence": "user_explicit",
                    "importance_reason": "可用于以后推荐",
                    "payload": {
                        "kind": "preference",
                        "subject": "用户",
                        "attribute": "饮品偏好",
                        "value": "喜欢无糖茶",
                        "conditions": "",
                        "scope": "reality",
                        "valid_time": {
                            "precision": "unknown",
                            "start": None,
                            "end": None,
                            "original_text": "",
                            "timezone": "",
                            "timezone_source": "unknown",
                        },
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
        ]


class CorrectionProvider:
    def extract(self, messages, existing_memories=None):
        user = next(item for item in messages if item["role"] == "user")
        target = existing_memories[0]
        return [
            {
                "action": "correct",
                "target_memory_id": target["memory_id"],
                "reason": "用户明确纠正居住地",
                "memory": {
                    "schema_version": "1.0",
                    "evidence": "user_explicit",
                    "importance_reason": "替换错误的当前事实",
                    "payload": {
                        "kind": "fact",
                        "subject": "用户",
                        "attribute": "居住地",
                        "value": "苏州",
                        "conditions": "",
                        "scope": "reality",
                        "valid_time": {
                            "precision": "unknown",
                            "start": None,
                            "end": None,
                            "original_text": "",
                            "timezone": "",
                            "timezone_source": "unknown",
                        },
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
        ]


class EventSupplementProvider:
    def extract(self, messages, existing_memories=None):
        user = next(item for item in messages if item["role"] == "user")
        payload = {
            "kind": "event",
            "title": "与小周的排班争执",
            "participants": ["用户", "小周"],
            "scene": "reality",
            "summary": (
                "双方已经说开，排班问题解决"
                if existing_memories
                else "双方因为排班发生争执"
            ),
            "outcome": "问题解决" if existing_memories else "",
            "open_question": "" if existing_memories else "如何解决争执",
            "occurred_at": {
                "precision": "day",
                "start": datetime.fromisoformat("2026-09-20T00:00:00+08:00"),
                "end": None,
                "original_text": "9月20日",
                "timezone": "Asia/Shanghai",
                "timezone_source": "client_reported",
            },
        }
        return [
            {
                "action": "supplement" if existing_memories else "create",
                "target_memory_id": existing_memories[0]["memory_id"]
                if existing_memories
                else None,
                "reason": "同一事件有新进展" if existing_memories else "重要现实事件",
                "memory": {
                    "schema_version": "1.0",
                    "evidence": "user_explicit",
                    "importance_reason": "后续交流需要知道事件进展",
                    "payload": payload,
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
        ]


def test_completed_turn_enqueues_jobs_and_automatic_extraction_deduplicates(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    chat = ConversationService(repo, type("Provider", (), {"generate": lambda _, __: "好"})())
    first = chat.send("alice", conversation_id, "one", "我喜欢无糖茶")
    second = chat.send("alice", conversation_id, "two", "我还是喜欢无糖茶")
    automation = MemoryAutomationService(sessions, ExtractionProvider())
    assert automation.process_turn(first.turn_id)[0]["status"] == "created"
    assert automation.process_turn(second.turn_id)[0]["status"] == "deduplicated"
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(PersonalMemory)) == 1
        assert session.scalar(select(func.count()).select_from(PersonalMemoryVersion)) == 1
        assert session.scalar(select(func.count()).select_from(MemoryJob)) == 4
        instance = session.get(CharacterInstance, instance_id)
        assert instance.data_revision == 1
        assert instance.context_revision == 0


def test_automatic_correction_receives_existing_candidate_and_versions_it(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    chat = ConversationService(repo, type("Provider", (), {"generate": lambda _, __: "好"})())
    first = chat.send("alice", conversation_id, "city-one", "我住在杭州")
    MemoryAutomationService(sessions, ExtractionProvider()).process_turn(first.turn_id)
    second = chat.send("alice", conversation_id, "city-two", "刚才说错了，我一直住苏州")

    result = MemoryAutomationService(sessions, CorrectionProvider()).process_turn(second.turn_id)

    assert result[0]["status"] == "corrected"
    with sessions() as session:
        memory = session.scalar(
            select(PersonalMemory).where(PersonalMemory.instance_id == instance_id)
        )
        assert memory.content == "用户的居住地：苏州"
        assert memory.revision == 2
        assert session.scalar(select(func.count()).select_from(PersonalMemoryVersion)) == 2


def test_event_supplement_updates_one_versioned_memory(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    chat = ConversationService(repo, type("Provider", (), {"generate": lambda _, __: "好"})())
    automation = MemoryAutomationService(sessions, EventSupplementProvider())
    first = chat.send("alice", conversation_id, "event-one", "9月20日我和小周因排班争执")
    assert automation.process_turn(first.turn_id)[0]["status"] == "created"
    second = chat.send("alice", conversation_id, "event-two", "我们今天已经说开了")

    assert automation.process_turn(second.turn_id)[0]["status"] == "supplemented"

    with sessions() as session:
        memories = list(
            session.scalars(
                select(PersonalMemory).where(PersonalMemory.instance_id == instance_id)
            )
        )
        assert len(memories) == 1
        assert memories[0].revision == 2
        assert "问题解决" in memories[0].content
        versions = list(
            session.scalars(
                select(PersonalMemoryVersion)
                .where(PersonalMemoryVersion.memory_id == memories[0].id)
                .order_by(PersonalMemoryVersion.revision)
            )
        )
        assert len(versions) == 2
        assert versions[0].payload["kind"] == "event"
        assert versions[1].payload["occurred_at"] == versions[0].payload["occurred_at"]


def test_explicit_operation_receipt_is_committed_and_idempotent(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    operations = ExplicitMemoryOperationService(sessions)
    first = operations.execute(
        "alice", instance_id, "remember-one", "remember", content="下月提醒我整理照片"
    )
    second = operations.execute(
        "alice", instance_id, "remember-one", "remember", content="不会重复写入"
    )
    assert first == second
    assert first["status"] == "committed"
    assert first["revision"] == 1
