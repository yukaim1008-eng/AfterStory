from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from afterstory.conversation import ConversationService
from afterstory.memory import MemoryService
from afterstory.memory_jobs import MemoryJobService
from afterstory.models import (
    CharacterInstance,
    MemoryJob,
    MemorySourceLink,
    Message,
    PersonalMemory,
    PersonalMemoryVersion,
)
from afterstory.repository import Repository


def test_manual_memory_writes_immutable_versions_and_separate_revisions(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    service = MemoryService(sessions)
    created = service.create("alice", instance_id, "create", "喜欢春雨")
    service.update("alice", created["memory_id"], 1, "喜欢春雨的声音")
    service.delete("alice", created["memory_id"], 2)

    with sessions() as session:
        memory = session.get(PersonalMemory, created["memory_id"])
        versions = list(
            session.scalars(
                select(PersonalMemoryVersion)
                .where(PersonalMemoryVersion.memory_id == memory.id)
                .order_by(PersonalMemoryVersion.revision)
            )
        )
        assert [(item.revision, item.operation, item.status) for item in versions] == [
            (1, "create", "active"),
            (2, "update", "active"),
            (3, "delete", "deleted"),
        ]
        assert versions[0].content == "喜欢春雨"
        assert versions[1].content == "喜欢春雨的声音"
        assert versions[2].content is None
        assert session.scalar(
            select(MemorySourceLink).where(MemorySourceLink.memory_version_id == versions[0].id)
        )
        instance = session.get(CharacterInstance, instance_id)
        assert instance.data_revision == 3
        assert instance.context_revision == 3


def test_job_keys_are_idempotent_and_expired_leases_can_be_recovered(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    jobs = MemoryJobService(sessions, lease_seconds=30)
    first = jobs.enqueue(instance_id, "turn:one:extract", "extract", {"turn_id": "one"}, 0)
    second = jobs.enqueue(instance_id, "turn:one:extract", "extract", {"turn_id": "one"}, 0)
    assert first == second
    claim = jobs.claim()
    assert claim["job_id"] == first

    with sessions.begin() as session:
        job = session.get(MemoryJob, first)
        job.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    recovered = jobs.claim()
    assert recovered["job_id"] == first
    assert recovered["lease_token"] != claim["lease_token"]
    assert not jobs.complete(first, claim["lease_token"])
    assert jobs.complete(first, recovered["lease_token"])


def test_new_messages_record_service_time_and_timezone_provenance(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    ConversationService(repo, type("Provider", (), {"generate": lambda _, __: "收到"})()).send(
        "alice",
        conversation_id,
        "time",
        "昨天的事",
        timezone_name="Asia/Shanghai",
        timezone_source="client_reported",
    )
    with sessions() as session:
        messages = list(session.scalars(select(Message).order_by(Message.role.desc())))
        user = next(item for item in messages if item.role == "user")
        assistant = next(item for item in messages if item.role == "assistant")
        assert user.recorded_at and user.timezone_name == "Asia/Shanghai"
        assert user.timezone_source == "client_reported"
        assert assistant.recorded_at and assistant.timezone_source == "server"
