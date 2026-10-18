from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select

from afterstory.api import create_app
from afterstory.auth import AuthService, token_digest, utcnow
from afterstory.auth.cli import main as accounts_main
from afterstory.config import Settings
from afterstory.domain import DomainError
from afterstory.models import CharacterInstance, RegistrationInvite, User

ORIGIN = {"Origin": "http://testserver"}


def register(client, username, password, code, headers=None):
    return client.post(
        "/api/auth/register",
        headers=headers if headers is not None else ORIGIN,
        json={"username": username, "password": password, "invite_code": code},
    )


def test_registration_http_contract_without_database():
    app = create_app(Settings(_env_file=None, llm_active_model="fake"))
    app.state.auth.register = lambda username, password, code, remote_ip: (
        SimpleNamespace(id="new-id", username=username.lower()),
        "test-session-token",
    )
    with TestClient(app) as client:
        response = register(client, "New.User", "new-user-password-123", "A" * 43)
        assert response.status_code == 201
        assert response.json()["username"] == "new.user"
        assert "HttpOnly" in response.headers["set-cookie"]
        assert register(client, "newuser", "new-user-password-123", "A" * 43, {}).status_code == 403
        assert register(client, "newuser", "short", "A" * 43).status_code == 422
        assert register(client, "newuser", "new-user-password-123", "short").status_code == 422
        assert (
            client.post(
                "/api/auth/register",
                headers=ORIGIN,
                json={
                    "username": "newuser",
                    "password": "new-user-password-123",
                    "invite_code": "A" * 43,
                    "is_admin": True,
                },
            ).status_code
            == 422
        )


def test_invite_registration_creates_isolated_account_and_session(database):
    cfg, sessions = database
    code, expires_at = AuthService(sessions).issue_invite()
    assert len(code) == 43
    assert expires_at > utcnow()
    with sessions.begin() as session:
        invite = session.get(RegistrationInvite, token_digest("invite:" + code))
        assert invite is not None
        assert code not in invite.token_hash
        assert invite.consumed_at is None

    with TestClient(create_app(cfg)) as client:
        response = register(client, "New.User", "new-user-password-123", code)
        assert response.status_code == 201
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        account_id = response.json()["user_id"]
        assert response.json()["username"] == "new.user"
        assert client.get("/api/auth/me").json()["user_id"] == account_id
        assert client.get("/api/history").json()["items"] == []
        assert register(client, "other.user", "other-user-password-123", code).json() == {
            "error": "invalid_invite"
        }
    with sessions.begin() as session:
        invite = session.get(RegistrationInvite, token_digest("invite:" + code))
        assert invite.consumed_by_user_id == account_id
        assert invite.consumed_at is not None
        assert session.get(User, account_id).username == "new.user"
        assert (
            session.scalar(select(CharacterInstance).where(CharacterInstance.user_id == account_id))
            is None
        )
        assert session.scalar(select(User.id).where(User.username == "other.user")) is None


def test_invalid_expired_revoked_invites_and_username_conflict(database):
    cfg, sessions = database
    auth = AuthService(sessions)
    code, _ = auth.issue_invite()
    with TestClient(create_app(cfg)) as client:
        assert register(client, "member", "member-password-123", code, {}).status_code == 403
        assert (
            register(client, "member", "member-password-123", code, {"Origin": "https://evil.test"})
            .status_code
            == 403
        )
        assert register(client, "member", "short", code).status_code == 422
        assert register(client, "alice", "member-password-123", code).json() == {
            "error": "username_taken"
        }
        assert register(client, "member", "member-password-123", code).status_code == 201

    expired_code, _ = auth.issue_invite()
    revoked_code, _ = auth.issue_invite()
    with sessions.begin() as session:
        session.get(RegistrationInvite, token_digest("invite:" + expired_code)).expires_at = (
            utcnow() - timedelta(seconds=1)
        )
    auth.revoke_invite(revoked_code)
    with TestClient(create_app(cfg)) as client:
        for unavailable in (expired_code, revoked_code, "A" * 43):
            assert register(client, "another", "another-password-123", unavailable).json() == {
                "error": "invalid_invite"
            }
    with sessions.begin() as session:
        assert session.scalar(select(User.id).where(User.username == "another")) is None


def test_registration_attempts_are_rate_limited(database):
    cfg, _ = database
    with TestClient(create_app(cfg)) as client:
        for _ in range(8):
            assert register(client, "someone", "someone-password-123", "A" * 43).status_code == 400
        assert register(client, "someone", "someone-password-123", "A" * 43).json() == {
            "error": "registration_rate_limited"
        }


def test_registration_uses_secure_host_cookie_in_production(database):
    cfg, sessions = database
    code, _ = AuthService(sessions).issue_invite()
    production = Settings(
        _env_file=None,
        database_url=cfg.database_url,
        llm_active_model="fake",
        app_env="production",
        allowed_hosts="testserver,afterstory.example",
    )
    with TestClient(create_app(production), base_url="https://testserver") as client:
        response = register(
            client,
            "newmember",
            "new-member-password-123",
            code,
            {"Origin": "https://testserver"},
        )
        assert response.status_code == 201
        assert "__Host-afterstory_session=" in response.headers["set-cookie"]
        assert "Secure" in response.headers["set-cookie"]


def test_concurrent_redemption_uses_invite_only_once(database):
    _, sessions = database
    auth = AuthService(sessions)
    code, _ = auth.issue_invite()

    def redeem(number):
        try:
            result = auth.register(
                f"member{number}", "member-password-123", code, f"ip-{number}"
            )
            return result[0].id
        except DomainError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(redeem, (1, 2)))
    assert results.count("invalid_invite") == 1
    with sessions.begin() as session:
        invite = session.get(RegistrationInvite, token_digest("invite:" + code))
        assert invite.consumed_by_user_id in results
        assert session.scalar(select(User.id).where(User.username.in_(("member1", "member2"))))


def test_admin_commands_issue_and_revoke_invite(database, monkeypatch, capsys):
    _, sessions = database
    assert accounts_main(["invite-create", "--days", "1"]) == 0
    output = capsys.readouterr().out
    code = output.split("邀请码（仅显示一次）：", 1)[1].splitlines()[0]
    monkeypatch.setattr("afterstory.auth.cli.getpass.getpass", lambda _: code)
    assert accounts_main(["invite-revoke"]) == 0
    with sessions.begin() as session:
        invite = session.get(RegistrationInvite, token_digest("invite:" + code))
        assert invite.revoked_at is not None
