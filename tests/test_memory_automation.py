from sqlalchemy import func, select

from afterstory.conversation import ConversationService
from afterstory.memory_automation import ExplicitMemoryOperationService, MemoryAutomationService
from afterstory.models import CharacterInstance, MemoryJob, PersonalMemory, PersonalMemoryVersion
from afterstory.repository import Repository


class ExtractionProvider:
    def extract(self, messages):
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
