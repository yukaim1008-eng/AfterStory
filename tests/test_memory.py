from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from afterstory.api import create_app, current_user
from afterstory.domain import DomainError
from afterstory.memory import MemoryService
from afterstory.models import CharacterInstance, PersonalMemory
from afterstory.repository import Repository


def make_chat(client, version="test-lan-v1"):
    instance_id = client.post("/instances", json={"version_id": version}).json()[
        "instance_id"
    ]
    conversation_id = client.post(
        "/conversations", json={"instance_id": instance_id}
    ).json()["conversation_id"]
    return instance_id, conversation_id


def completed_user_message(client, conversation_id, request_id="turn-1", text="我喜欢雨天"):
    response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"request_id": request_id, "text": text},
    )
    assert response.status_code == 200
    history = client.get(f"/conversations/{conversation_id}/messages").json()
    return next(
        message
        for turn in history["turns"]
        for message in turn["messages"]
        if message["role"] == "user"
    )


def test_manual_memory_lifecycle_and_source_location(database):
    cfg, sessions = database
    with TestClient(create_app(cfg)) as client:
        instance_id, conversation_id = make_chat(client)
        source = completed_user_message(client, conversation_id)
        path = f"/instances/{instance_id}/memories"
        body = {
            "request_id": "remember-1",
            "content": "我喜欢雨天",
            "source_message_id": source["message_id"],
        }
        created = client.post(path, json=body)
        assert created.status_code == 201
        memory = created.json()
        assert memory["kind"] == "fact"
        assert memory["revision"] == 1
        assert memory["source"]["conversation_id"] == conversation_id

        assert client.post(path, json=body).json() == memory
        assert client.post(path, json={**body, "content": "不同内容"}).status_code == 409
        assert (
            client.post(path, json={**body, "request_id": "remember-2"}).status_code
            == 409
        )

        listing = client.get(path, params={"limit": 1}).json()
        assert listing["total"] == 1
        assert listing["items"][0]["memory_id"] == memory["memory_id"]

        updated = client.patch(
            f"/memories/{memory['memory_id']}",
            json={"expected_revision": 1, "content": "我更喜欢下小雨的夜晚"},
        )
        assert updated.status_code == 200
        assert updated.json()["revision"] == 2
        assert client.patch(
            f"/memories/{memory['memory_id']}",
            json={"expected_revision": 1, "content": "旧页面覆盖"},
        ).status_code == 409

        deleted = client.delete(
            f"/memories/{memory['memory_id']}", params={"expected_revision": 2}
        )
        assert deleted.status_code == 200
        assert deleted.json()["content"] is None
        assert deleted.json()["status"] == "deleted"
        assert client.delete(
            f"/memories/{memory['memory_id']}", params={"expected_revision": 2}
        ).status_code == 200
        assert client.get(path).json()["total"] == 0
        assert client.post(path, json=body).status_code == 409
        assert client.post(path, json={**body, "request_id": "remember-3"}).status_code == 409

        # Deleting a memory never deletes or rewrites the original chat message.
        history = client.get(f"/conversations/{conversation_id}/messages").json()
        assert source["message_id"] in {
            message["message_id"]
            for turn in history["turns"]
            for message in turn["messages"]
        }
    with sessions() as session:
        instance = session.get(CharacterInstance, instance_id)
        assert instance.context_revision == 3
        assert instance.history_floor_revision == 3


def test_memory_source_and_user_isolation(database):
    cfg, _ = database
    app = create_app(cfg)
    with TestClient(app) as client:
        first_instance, first_conversation = make_chat(client)
        second_instance, _ = make_chat(client, "test-xiao-v1")
        source = completed_user_message(client, first_conversation)
        assistant = next(
            message
            for turn in client.get(
                f"/conversations/{first_conversation}/messages"
            ).json()["turns"]
            for message in turn["messages"]
            if message["role"] == "assistant"
        )
        assert client.post(
            f"/instances/{second_instance}/memories",
            json={
                "request_id": "wrong-instance",
                "content": "private source",
                "source_message_id": source["message_id"],
            },
        ).status_code == 404
        assert client.post(
            f"/instances/{first_instance}/memories",
            json={
                "request_id": "assistant-source",
                "content": "not a personal fact",
                "source_message_id": assistant["message_id"],
            },
        ).status_code == 404
        saved = client.post(
            f"/instances/{first_instance}/memories",
            json={"request_id": "manual", "content": "仅 Alice 可见"},
        ).json()
        app.dependency_overrides[current_user] = lambda: "bob"
        assert client.get(f"/instances/{first_instance}/memories").status_code == 404
        assert client.patch(
            f"/memories/{saved['memory_id']}",
            json={"expected_revision": 1, "content": "read private"},
        ).status_code == 404
        assert client.delete(
            f"/memories/{saved['memory_id']}", params={"expected_revision": 1}
        ).status_code == 404


def test_concurrent_memory_correction_has_one_winner(database):
    _, sessions = database
    repository = Repository(sessions)
    instance_id = repository.create_instance("alice", "test-lan-v1")["instance_id"]
    service = MemoryService(sessions)
    memory = service.create("alice", instance_id, "request", "初始内容")

    def correct(content):
        try:
            return service.update("alice", memory["memory_id"], 1, content)
        except DomainError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(correct, ["版本 A", "版本 B"]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count("memory_revision_conflict") == 1
    with sessions() as session:
        stored = session.scalar(select(PersonalMemory))
        assert stored.revision == 2
        assert stored.content in {"版本 A", "版本 B"}


@pytest.mark.parametrize("content", ["", " ", "x" * 2001])
def test_memory_input_validation(database, content):
    cfg, _ = database
    with TestClient(create_app(cfg)) as client:
        instance_id, _ = make_chat(client)
        assert client.post(
            f"/instances/{instance_id}/memories",
            json={"request_id": "request", "content": content},
        ).status_code == 422
