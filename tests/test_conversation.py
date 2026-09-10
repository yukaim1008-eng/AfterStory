from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from afterstory.api import create_app, current_user
from afterstory.conversation import ConversationService
from afterstory.domain import DomainError, ProviderError
from afterstory.models import Turn
from afterstory.repository import Repository


class RecordingProvider:
    def __init__(self):
        self.calls = []

    def generate(self, messages):
        self.calls.append(messages)
        return "测试回复"


def setup_conversation(client, version="test-lan-v1"):
    instance = client.post("/instances", json={"version_id": version})
    assert instance.status_code == 201
    conversation = client.post(
        "/conversations", json={"instance_id": instance.json()["instance_id"]}
    )
    assert conversation.status_code == 201
    return conversation.json()["conversation_id"], instance.json()["instance_id"]


def test_multiturn_restart_and_idempotency(database):
    cfg, _ = database
    provider = RecordingProvider()
    with TestClient(create_app(cfg, provider)) as client:
        assert client.get("/health").status_code == 200
        conversation, _ = setup_conversation(client)
        path = f"/conversations/{conversation}/messages"
        for i in range(3):
            result = client.post(path, json={"request_id": str(i), "text": f"消息{i}"})
            assert result.status_code == 200
            assert result.json()["audio_status"] == "not_requested"
        assert [m.role for m in provider.calls[-1]] == [
            "system",
            "user",
            "assistant",
            "user",
            "assistant",
            "user",
        ]
        duplicate = client.post(path, json={"request_id": "2", "text": "消息2"})
        assert duplicate.json() == result.json()
        assert len(provider.calls) == 3
        assert client.post(path, json={"request_id": "2", "text": "changed"}).status_code == 409
    with TestClient(create_app(cfg, provider)) as restarted:
        history = restarted.get(path, params={"offset": 1, "limit": 1}).json()
        assert history["total"] == 3
        assert history["turns"][0]["sequence"] == 2
        assert restarted.post(path, json={"request_id": "3", "text": "继续"}).status_code == 200
        assert len(provider.calls[-1]) == 8


def test_user_character_instance_isolation(database):
    cfg, _ = database
    provider = RecordingProvider()
    app = create_app(cfg, provider)
    with TestClient(app) as client:
        ids = [
            setup_conversation(client, v) for v in ("test-lan-v1", "test-xiao-v1", "test-lan-v1")
        ]
        for index, (conversation, _) in enumerate(ids):
            client.post(
                f"/conversations/{conversation}/messages",
                json={"request_id": "same", "text": f"private-{index}"},
            )
            assert len(provider.calls[-1]) == 2
        assert provider.calls[0][0].content != provider.calls[1][0].content
        app.dependency_overrides[current_user] = lambda: "bob"
        for conversation, instance in ids:
            path = f"/conversations/{conversation}/messages"
            assert client.get(path).status_code == 404
            assert client.post(path, json={"request_id": "x", "text": "x"}).status_code == 404
            assert client.post("/conversations", json={"instance_id": instance}).status_code == 404
        assert (
            client.post(
                "/instances", json={"version_id": "test-lan-v1", "user_id": "alice"}
            ).status_code
            == 422
        )


def test_failure_retry_and_empty_input(database):
    cfg, _ = database

    class Flaky(RecordingProvider):
        def generate(self, messages):
            self.calls.append(messages)
            if len(self.calls) == 1:
                raise ProviderError("llm_timeout")
            return "恢复成功"

    provider = Flaky()
    with TestClient(create_app(cfg, provider)) as client:
        conversation, _ = setup_conversation(client)
        path = f"/conversations/{conversation}/messages"
        assert client.post(path, json={"request_id": "a", "text": "  "}).status_code == 422
        body = {"request_id": "a", "text": "你好"}
        assert client.post(path, json=body).json() == {"error": "llm_timeout"}
        failed = client.get(path).json()["turns"][0]
        assert failed["status"] == "failed"
        assert len(failed["messages"]) == 1
        assert client.post(path, json=body).status_code == 200
        assert len(client.get(path).json()["turns"][0]["messages"]) == 2
        assert len(provider.calls[-1]) == 2


def test_expired_attempt_cannot_overwrite_retry(database):
    _, sessions = database
    repo = Repository(sessions)
    instance = repo.create_instance("alice", "test-lan-v1")
    conversation = repo.create_conversation("alice", instance["instance_id"])["conversation_id"]
    old_id, old_attempt, _ = repo.begin_turn("alice", conversation, "r1", "你好")
    with sessions.begin() as session:
        session.get(Turn, old_id).lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    new_id, new_attempt, _ = repo.begin_turn("alice", conversation, "r1", "你好")
    assert old_id == new_id and old_attempt != new_attempt
    with pytest.raises(DomainError) as exc:
        repo.finish_turn("alice", conversation, old_id, old_attempt, text="old")
    assert exc.value.code == "turn_attempt_superseded"
    repo.finish_turn("alice", conversation, new_id, new_attempt, text="new")
    assert repo.history("alice", conversation, 0, 20)["turns"][0]["messages"][1]["text"] == "new"


def test_concurrent_request_busy(database):
    _, sessions = database
    repo = Repository(sessions)
    instance = repo.create_instance("alice", "test-lan-v1")
    conversation = repo.create_conversation("alice", instance["instance_id"])["conversation_id"]
    entered, release = Event(), Event()

    class Blocking:
        def generate(self, messages):
            entered.set()
            assert release.wait(5)
            return "done"

    service = ConversationService(repo, Blocking())
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.send, "alice", conversation, "a", "hello")
        try:
            assert entered.wait(5)
            with pytest.raises(DomainError) as exc:
                service.send("alice", conversation, "b", "second")
            assert exc.value.code == "conversation_busy"
        finally:
            release.set()
        first.result(timeout=5)
    with sessions() as session:
        assert len(list(session.scalars(select(Turn)))) == 1


def test_stale_failed_turn_retry_rejected(database):
    _, sessions = database
    repo = Repository(sessions)
    instance = repo.create_instance("alice", "test-lan-v1")
    conversation = repo.create_conversation("alice", instance["instance_id"])["conversation_id"]
    turn, attempt, _ = repo.begin_turn("alice", conversation, "a", "first")
    repo.finish_turn("alice", conversation, turn, attempt, error="llm_timeout")
    turn, attempt, _ = repo.begin_turn("alice", conversation, "b", "second")
    repo.finish_turn("alice", conversation, turn, attempt, text="ok")
    with pytest.raises(DomainError) as exc:
        repo.begin_turn("alice", conversation, "a", "first")
    assert exc.value.code == "stale_turn_retry"
