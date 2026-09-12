from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from afterstory.api import create_app, current_user
from afterstory.domain import ProviderError
from afterstory.models import Conversation, Turn


def make_chat(client, version="test-lan-v1"):
    instance = client.post("/instances", json={"version_id": version}).json()["instance_id"]
    return client.post("/conversations", json={"instance_id": instance}).json()["conversation_id"]


def test_catalog_pagination_old_versions_and_source_location(database):
    cfg, sessions = database
    app = create_app(cfg)
    with TestClient(app) as client:
        ids = [make_chat(client) for _ in range(3)]
        sources = []
        for conversation in ids:
            for index in range(4):
                response = client.post(
                    f"/api/conversations/{conversation}/messages",
                    json={
                        "request_id": str(index),
                        "text": f"message {index}",
                    },
                )
                assert response.status_code == 200
                sources.append(response.json()["turn_id"])
        # Equal timestamps use a stable conversation ID tiebreaker.
        with sessions.begin() as session:
            for turn in session.scalars(select(Turn)):
                turn.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
                turn.updated_at = turn.created_at
        first = client.get("/api/history?limit=2").json()
        second = client.get("/api/history?offset=2&limit=2").json()
        assert first["total"] == 3
        assert [i["conversation_id"] for i in first["items"] + second["items"]] == sorted(ids)
        info = client.get(f"/api/conversations/{ids[0]}").json()
        assert info["character_id"] == "test-lan"
        assert info["version_id"] == "test-lan-v1"
        assert info["created_at"] and info["checkpoint"]
        located = client.get(
            f"/api/conversations/{ids[0]}/messages?around_turn_id={sources[2]}&limit=2"
        ).json()
        assert sources[2] in [t["turn_id"] for t in located["turns"]]
        assert located["offset"] == 1
        assert (
            client.get(
                f"/api/conversations/{ids[0]}/messages?around_turn_id={sources[-1]}"
            ).status_code
            == 404
        )
        assert client.get("/api/history?limit=101").status_code == 422
        app.dependency_overrides[current_user] = lambda: "bob"
        assert client.get("/api/history").json()["total"] == 0
        assert client.get(f"/api/conversations/{ids[0]}").status_code == 404
        assert (
            client.get(
                f"/api/conversations/{ids[0]}/messages?around_turn_id={sources[0]}"
            ).status_code
            == 404
        )


def test_history_timestamp_migration_preserves_legacy_data(database):
    cfg, sessions = database
    with TestClient(create_app(cfg)) as client:
        conversation = make_chat(client)
        client.post(
            f"/conversations/{conversation}/messages", json={"request_id": "1", "text": "keep"}
        )
    migration = Config("alembic.ini")
    command.downgrade(migration, "b9055da31d3d")
    command.upgrade(migration, "head")
    with sessions() as session:
        assert session.get(Conversation, conversation).created_at is None
        assert session.scalar(select(Turn)).created_at is None
        assert session.scalar(text("SELECT count(*) FROM messages")) == 2
    with TestClient(create_app(cfg)) as client:
        info = client.get(f"/api/conversations/{conversation}").json()
        assert info["last_activity_at"] is None
        new_conversation = make_chat(client)
        assert client.get(f"/api/conversations/{new_conversation}").json()["created_at"]
    command.check(migration)


def test_successful_retry_moves_old_conversation_to_latest_activity(database):
    cfg, sessions = database

    class Provider:
        fail = True

        def generate(self, messages):
            if self.fail:
                self.fail = False
                raise ProviderError("llm_timeout")
            return "reply"

    with TestClient(create_app(cfg, Provider())) as client:
        first, second = make_chat(client), make_chat(client)
        body = {"request_id": "retry", "text": "hello"}
        assert client.post(f"/conversations/{first}/messages", json=body).status_code == 502
        with sessions.begin() as session:
            turn = session.scalar(select(Turn))
            turn.created_at = None  # Migration-era failed message with an unknown original time.
            turn.updated_at = None
        assert client.post(f"/conversations/{second}/messages", json=body).status_code == 200
        assert client.post(f"/conversations/{first}/messages", json=body).status_code == 200
        listing = client.get("/history").json()["items"]
        assert listing[0]["conversation_id"] == first
        assert listing[0]["last_activity_at"]
        with sessions() as session:
            assert (
                session.scalar(select(Turn).where(Turn.conversation_id == first)).created_at is None
            )
