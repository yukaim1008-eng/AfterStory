from datetime import timedelta

from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from afterstory.api import create_app
from afterstory.auth import AuthService, token_digest, utcnow
from afterstory.config import Settings
from afterstory.conversation.repository import Repository
from afterstory.models import AuthSession, CharacterInstance, User


def login(client, username="alice", password="alice-test-password-123"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_anonymous_login_csrf_logout_and_old_user_isolation(database):
    cfg, sessions = database
    old = Repository(sessions).open_session("bob", "test-lan-v1")
    app = create_app(cfg)
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/auth/me").status_code == 401
        assert login(client, username="无效用户名", password="wrong").status_code == 401
        assert client.get("/api/history").status_code == 401
        assert (
            client.post("/api/sessions/open", json={"version_id": "test-lan-v1"}).status_code == 401
        )
        assert login(client, password="wrong").json() == {"error": "invalid_credentials"}
        response = login(client)
        assert response.status_code == 200
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        assert "Secure" not in response.headers["set-cookie"]
        assert response.json()["user_id"] == "alice"
        assert client.get("/api/auth/me").json()["username"] == "alice"
        assert client.get("/api/history").json()["items"] == []
        assert client.get(f"/api/conversations/{old['conversation_id']}").status_code == 404
        assert (
            client.post("/api/sessions/open", json={"version_id": "test-lan-v1"}).status_code == 403
        )
        csrf = response.json()["csrf_token"]
        assert (
            client.post(
                "/api/sessions/open",
                headers={"X-CSRF-Token": csrf},
                json={"version_id": "test-lan-v1"},
            ).status_code
            == 200
        )
        assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
        assert client.get("/api/auth/me").status_code == 401


def test_new_account_has_independent_identity_and_reset_revokes_sessions(database):
    cfg, sessions = database
    auth = AuthService(sessions)
    new_id = auth.create_account("First.User", "new-user-password-123")
    assert new_id not in {"alice", "bob"}
    with sessions.begin() as session:
        assert session.get(User, "bob").username is None
        assert (
            session.scalar(select(CharacterInstance).where(CharacterInstance.user_id == new_id))
            is None
        )
    with TestClient(create_app(cfg)) as client:
        result = login(client, "first.user", "new-user-password-123")
        assert result.status_code == 200
        assert client.get("/api/auth/me").json()["user_id"] == new_id
        csrf = result.json()["csrf_token"]
        assert (
            client.post(
                "/api/auth/password",
                headers={"X-CSRF-Token": csrf},
                json={"current_password": "wrong", "new_password": "changed-password-123"},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/auth/password",
                headers={"X-CSRF-Token": csrf},
                json={
                    "current_password": "new-user-password-123",
                    "new_password": "changed-password-123",
                },
            ).status_code
            == 200
        )
        assert client.get("/api/auth/me").status_code == 401
        assert login(client, "first.user", "new-user-password-123").status_code == 401
        assert login(client, "first.user", "changed-password-123").status_code == 200
        auth.reset_password("first.user", "reset-password-123")
        assert client.get("/api/auth/me").status_code == 401


def test_expired_and_idle_sessions_are_rejected(database):
    cfg, sessions = database
    with TestClient(create_app(cfg)) as client:
        assert login(client).status_code == 200
        with sessions.begin() as session:
            row = session.scalar(select(AuthSession).where(AuthSession.user_id == "alice"))
            row.last_used_at = utcnow() - timedelta(days=8)
        assert client.get("/api/auth/me").status_code == 401
        assert login(client).status_code == 200
        with sessions.begin() as session:
            token = client.cookies.get("afterstory_session")
            row = session.get(AuthSession, token_digest(token))
            row.expires_at = utcnow() - timedelta(seconds=1)
        assert client.get("/api/auth/me").status_code == 401


def test_login_rate_limit_and_cross_site_origin(database):
    cfg, _ = database
    with TestClient(create_app(cfg)) as client:
        assert login(client).status_code == 200
        csrf = client.get("/api/auth/me").json()["csrf_token"]
        assert (
            client.post(
                "/api/auth/logout", headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"}
            ).status_code
            == 200
        )  # Logout is guarded by the CSRF token, not Origin.
        assert (
            client.post(
                "/api/auth/login",
                headers={"Origin": "https://evil.example"},
                json={"username": "alice", "password": "alice-test-password-123"},
            ).status_code
            == 403
        )
        for _ in range(8):
            assert login(client, password="wrong").status_code == 401
        assert login(client).status_code == 429


def test_production_requires_host_and_sets_secure_host_cookie(database):
    cfg, _ = database
    try:
        Settings(_env_file=None, app_env="production", llm_active_model="fake")
    except ValidationError:
        pass
    else:
        raise AssertionError("production must reject default development hosts")
    production = Settings(
        _env_file=None,
        database_url=cfg.database_url,
        llm_active_model="fake",
        app_env="production",
        allowed_hosts="testserver,afterstory.example",
    )
    with TestClient(create_app(production), base_url="https://testserver") as client:
        response = client.post(
            "/api/auth/login",
            headers={"Origin": "https://testserver"},
            json={"username": "alice", "password": "alice-test-password-123"},
        )
        assert response.status_code == 200
        assert "__Host-afterstory_session=" in response.headers["set-cookie"]
        assert "Secure" in response.headers["set-cookie"]
        assert client.get("/api/auth/me").status_code == 200
