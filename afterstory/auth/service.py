"""Server-side password and browser session boundary."""

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from afterstory.domain import DomainError
from afterstory.models import AuthLoginAttempt, AuthSession, RegistrationInvite, User

PASSWORDS = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
DUMMY_HASH = PASSWORDS.hash("unusable-dummy-password")
USERNAME_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{2,31}\Z")
SESSION_LIFETIME = timedelta(days=30)
SESSION_IDLE = timedelta(days=7)
LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_LIMIT = 8
INVITE_DEFAULT_DAYS = 7
INVITE_MAX_DAYS = 90


def utcnow():
    return datetime.now(timezone.utc)


def normalize_username(value: str):
    username = value.strip().lower()
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError("用户名须为 3–32 位小写英文字母、数字、点、下划线或连字符")
    return username


def validate_password(value: str):
    if not 12 <= len(value) <= 128:
        raise ValueError("密码长度须为 12–128 个字符")
    return value


def token_digest(token: str):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def csrf_token(token: str):
    return hmac.new(token.encode("ascii"), b"afterstory-csrf-v1", hashlib.sha256).hexdigest()


class AuthService:
    def __init__(self, sessions):
        self.sessions = sessions

    def create_account(self, username: str, password: str):
        username = normalize_username(username)
        password_hash = PASSWORDS.hash(validate_password(password))
        with self.sessions.begin() as session:
            if session.scalar(select(User.id).where(User.username == username)):
                raise ValueError("用户名已存在")
            user = User(id=secrets.token_hex(16), username=username, password_hash=password_hash)
            session.add(user)
            session.flush()
            return user.id

    def issue_invite(self, days: int = INVITE_DEFAULT_DAYS):
        if not 1 <= days <= INVITE_MAX_DAYS:
            raise ValueError(f"邀请码有效期须为 1–{INVITE_MAX_DAYS} 天")
        code = secrets.token_urlsafe(32)
        expires_at = utcnow() + timedelta(days=days)
        with self.sessions.begin() as session:
            session.add(
                RegistrationInvite(
                    token_hash=token_digest("invite:" + code),
                    expires_at=expires_at,
                )
            )
        return code, expires_at

    def revoke_invite(self, code: str):
        with self.sessions.begin() as session:
            invite = session.get(
                RegistrationInvite, token_digest("invite:" + code), with_for_update=True
            )
            if invite is None or invite.consumed_at is not None or invite.revoked_at is not None:
                raise ValueError("邀请码不存在或已失效")
            invite.revoked_at = utcnow()

    def register(self, username_input: str, password: str, code: str, remote_ip: str):
        username = normalize_username(username_input)
        validate_password(password)
        if len(code) != 43 or not re.fullmatch(r"[A-Za-z0-9_-]{43}", code):
            raise DomainError(400, "invalid_invite")
        scope = token_digest("register-ip:" + remote_ip)
        error = None
        try:
            with self.sessions.begin() as session:
                # Serialize failed attempts by IP, then lock the invite for single-use redemption.
                session.execute(select(func.pg_advisory_xact_lock(int(scope[:15], 16))))
                now = utcnow()
                session.execute(
                    delete(AuthLoginAttempt).where(
                        AuthLoginAttempt.occurred_at < now - LOGIN_WINDOW
                    )
                )
                failures = session.scalar(
                    select(func.count())
                    .select_from(AuthLoginAttempt)
                    .where(
                        AuthLoginAttempt.scope_hash == scope,
                        AuthLoginAttempt.occurred_at >= now - LOGIN_WINDOW,
                    )
                )
                if failures >= LOGIN_LIMIT:
                    error = DomainError(429, "registration_rate_limited")
                else:
                    invite = session.get(
                        RegistrationInvite, token_digest("invite:" + code), with_for_update=True
                    )
                    if (
                        invite is None
                        or invite.expires_at <= now
                        or invite.consumed_at is not None
                        or invite.revoked_at is not None
                    ):
                        error = DomainError(400, "invalid_invite")
                    elif session.scalar(select(User.id).where(User.username == username)):
                        error = DomainError(409, "username_taken")
                    if error:
                        session.add(AuthLoginAttempt(scope_hash=scope))
                    else:
                        user = User(
                            id=secrets.token_hex(16),
                            username=username,
                            password_hash=PASSWORDS.hash(password),
                        )
                        session.add(user)
                        session.flush()
                        token = secrets.token_urlsafe(32)
                        session.add(
                            AuthSession(
                                token_hash=token_digest(token),
                                user_id=user.id,
                                expires_at=now + SESSION_LIFETIME,
                            )
                        )
                        invite.consumed_at = now
                        invite.consumed_by_user_id = user.id
                        return user, token
        except IntegrityError as exc:
            if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == (
                "uq_users_username"
            ):
                raise DomainError(409, "username_taken") from exc
            raise
        raise error

    def reset_password(self, username: str, password: str):
        username = normalize_username(username)
        password_hash = PASSWORDS.hash(validate_password(password))
        with self.sessions.begin() as session:
            user = session.scalar(select(User).where(User.username == username).with_for_update())
            if user is None:
                raise ValueError("账号不存在")
            user.password_hash = password_hash
            session.execute(
                update(AuthSession)
                .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=utcnow())
            )

    def login(self, username_input: str, password: str, remote_ip: str):
        try:
            username = normalize_username(username_input)
        except ValueError:
            username = username_input.strip().lower()[:64]
        now = utcnow()
        scopes = [
            token_digest("user:" + username),
            token_digest("ip:" + remote_ip),
        ]
        with self.sessions.begin() as session:
            # A transaction-level lock serializes concurrent attempts for each IP.
            session.execute(select(func.pg_advisory_xact_lock(int(scopes[1][:15], 16))))
            session.execute(
                delete(AuthLoginAttempt).where(AuthLoginAttempt.occurred_at < now - LOGIN_WINDOW)
            )
            session.execute(delete(AuthSession).where(AuthSession.expires_at < now))
            failures = [
                session.scalar(
                    select(func.count())
                    .select_from(AuthLoginAttempt)
                    .where(
                        AuthLoginAttempt.scope_hash == scope,
                        AuthLoginAttempt.occurred_at >= now - LOGIN_WINDOW,
                    )
                )
                for scope in scopes
            ]
            if any(count >= LOGIN_LIMIT for count in failures):
                raise DomainError(429, "login_rate_limited")
            user = session.scalar(select(User).where(User.username == username))
            valid = False
            candidate_hash = (
                user.password_hash if user and user.is_active and user.password_hash else DUMMY_HASH
            )
            if len(password) <= 128:
                try:
                    valid = PASSWORDS.verify(candidate_hash, password)
                except (VerifyMismatchError, ValueError):
                    pass
            valid = valid and user is not None and user.is_active and bool(user.password_hash)
            if not valid:
                session.add_all(AuthLoginAttempt(scope_hash=scope) for scope in scopes)
                # DomainError must be raised after the transaction commits the failure.
            else:
                token = secrets.token_urlsafe(32)
                session.add(
                    AuthSession(
                        token_hash=token_digest(token),
                        user_id=user.id,
                        expires_at=now + SESSION_LIFETIME,
                    )
                )
                return user, token
        raise DomainError(401, "invalid_credentials")

    def resolve(self, token: str | None):
        if not token or len(token) > 128:
            raise DomainError(401, "authentication_required")
        now = utcnow()
        with self.sessions.begin() as session:
            row = session.execute(
                select(AuthSession, User)
                .join(User, User.id == AuthSession.user_id)
                .where(AuthSession.token_hash == token_digest(token))
            ).one_or_none()
            if row is None:
                raise DomainError(401, "authentication_required")
            auth_session, user = row
            if (
                auth_session.revoked_at is not None
                or auth_session.expires_at <= now
                or auth_session.last_used_at <= now - SESSION_IDLE
                or not user.is_active
                or not user.password_hash
            ):
                raise DomainError(401, "authentication_required")
            if auth_session.last_used_at <= now - timedelta(minutes=5):
                auth_session.last_used_at = now
            return {"user_id": user.id, "username": user.username}

    def revoke(self, token: str | None):
        if not token or len(token) > 128:
            return
        with self.sessions.begin() as session:
            session.execute(
                update(AuthSession)
                .where(
                    AuthSession.token_hash == token_digest(token), AuthSession.revoked_at.is_(None)
                )
                .values(revoked_at=utcnow())
            )

    def change_password(self, user_id: str, current_password: str, new_password: str):
        password_hash = PASSWORDS.hash(validate_password(new_password))
        with self.sessions.begin() as session:
            user = session.get(User, user_id, with_for_update=True)
            if user is None or not user.password_hash:
                raise DomainError(401, "authentication_required")
            try:
                valid = PASSWORDS.verify(user.password_hash, current_password)
            except (VerifyMismatchError, ValueError):
                valid = False
            if not valid:
                raise DomainError(401, "invalid_credentials")
            user.password_hash = password_hash
            session.execute(
                update(AuthSession)
                .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=utcnow())
            )
