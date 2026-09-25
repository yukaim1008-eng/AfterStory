from sqlalchemy import select

from afterstory.conversation import ConversationService
from afterstory.memory_worker import MemoryRuntimeWorker
from afterstory.models import MemoryJob, PersonalMemory
from afterstory.repository import Repository


class StructuredFake:
    def extract(self, messages):
        user = next(item for item in messages if item["role"] == "user")
        return [
            {
                "action": "create",
                "target_memory_id": None,
                "reason": "明确长期偏好",
                "memory": {
                    "schema_version": "1.0",
                    "evidence": "user_explicit",
                    "importance_reason": "未来对话有用",
                    "payload": {
                        "kind": "fact",
                        "subject": "用户",
                        "attribute": "作息",
                        "value": "周末早起",
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
        ]

    def summarize(self, messages):
        raise AssertionError("insufficient segment should not call summary provider")


def test_persistent_worker_consumes_turn_job_with_fake_structured_provider(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    ConversationService(repo, type("Reply", (), {"generate": lambda _, __: "知道了"})()).send(
        "alice", conversation_id, "worker", "我周末会早起"
    )
    fake = StructuredFake()
    worker = MemoryRuntimeWorker(sessions, fake, fake)
    assert worker.run_once()
    assert worker.run_once()
    with sessions() as session:
        assert session.scalar(select(PersonalMemory)).content.endswith("周末早起")
        extract = session.scalar(select(MemoryJob).where(MemoryJob.job_type == "extract"))
        assert extract.status == "completed"
