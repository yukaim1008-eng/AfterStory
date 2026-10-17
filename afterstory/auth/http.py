"""Browser session and same-origin request boundary."""

import secrets

from fastapi import Request

from afterstory.auth.service import csrf_token
from afterstory.domain import DomainError


def session_cookie_name(settings):
    return "__Host-afterstory_session" if settings.app_env == "production" else "afterstory_session"


def browser_session(request: Request):
    return request.cookies.get(session_cookie_name(request.app.state.settings))


def check_csrf(request: Request, token: str | None):
    supplied = request.headers.get("x-csrf-token", "")
    if not token or not secrets.compare_digest(supplied, csrf_token(token)):
        raise DomainError(403, "csrf_invalid")


def check_login_origin(request: Request):
    origin = request.headers.get("origin")
    if origin:
        from urllib.parse import urlparse

        parsed = urlparse(origin)
        host = request.headers.get("host", "")
        allowed = {f"https://{host}"}
        if request.app.state.settings.app_env == "development":
            allowed.update(
                {
                    f"http://{host}",
                    "http://127.0.0.1:5173",
                    "http://localhost:5173",
                }
            )
        if parsed.scheme + "://" + parsed.netloc not in allowed or parsed.path not in {"", "/"}:
            raise DomainError(403, "origin_invalid")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise DomainError(403, "origin_invalid")


def current_user(request: Request):
    token = browser_session(request)
    identity = request.app.state.auth.resolve(token)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_csrf(request, token)
    return identity["user_id"]
