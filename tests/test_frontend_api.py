from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from afterstory.api import create_app, current_user
from afterstory.repository import Repository


def test_resume_is_atomic_and_user_scoped(database):
    cfg, sessions = database
    repository = Repository(sessions)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: repository.open_session("alice", "test-lan-v1"), range(4))
        )
    assert len({r["conversation_id"] for r in results}) == 1
    other = repository.open_session("bob", "test-lan-v1")
    assert other["conversation_id"] != results[0]["conversation_id"]
    app = create_app(cfg)
    with TestClient(app) as client:
        result = client.post("/api/sessions/open", json={"version_id": "test-lan-v1"})
        assert result.json() == results[0]
        assert client.get("/api/health").json()["capabilities"]["memory"] is False
        path = f"/api/conversations/{result.json()['conversation_id']}/messages"
        assert client.post(path, json={"request_id": "one", "text": "Hello"}).status_code == 200
        listing = client.get("/api/conversations").json()
        assert len(listing) == 1
        assert listing[0]["turns"] == 1
        assert listing[0]["preview"]
        app.dependency_overrides[current_user] = lambda: "bob"
        assert client.get("/api/conversations").json() == []
        assert client.get(path).status_code == 404
        assert client.post("/api/sessions/open", json={"version_id": "missing"}).status_code == 404
