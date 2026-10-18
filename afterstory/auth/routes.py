"""Account and session HTTP routes."""

from fastapi import APIRouter, Request, Response
from pydantic import Field

from afterstory.api_types import Input
from afterstory.auth.http import (
    browser_session,
    check_csrf,
    check_login_origin,
    session_cookie_name,
)
from afterstory.auth.service import csrf_token


class LoginInput(Input):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegistrationInput(Input):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_.-]{2,31}$")
    password: str = Field(min_length=12, max_length=128)
    invite_code: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]{43}$")


class PasswordChangeInput(Input):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


def set_session_cookie(response: Response, settings, token: str):
    response.set_cookie(
        session_cookie_name(settings),
        token,
        max_age=30 * 24 * 60 * 60,
        secure=settings.app_env == "production",
        httponly=True,
        samesite="strict",
        path="/",
    )


def build_router(auth, settings, memory_worker_enabled):
    router = APIRouter()

    @router.post("/auth/login")
    def login(body: LoginInput, request: Request, response: Response):
        check_login_origin(request)
        user, token = auth.login(
            body.username, body.password, request.client.host if request.client else ""
        )
        set_session_cookie(response, settings, token)
        return {"user_id": user.id, "username": user.username, "csrf_token": csrf_token(token)}

    @router.post("/auth/register", status_code=201)
    def register(body: RegistrationInput, request: Request, response: Response):
        check_login_origin(request, require_origin=True)
        user, token = auth.register(
            body.username,
            body.password,
            body.invite_code,
            request.client.host if request.client else "",
        )
        set_session_cookie(response, settings, token)
        return {"user_id": user.id, "username": user.username, "csrf_token": csrf_token(token)}

    @router.get("/auth/me")
    def me(request: Request):
        token = browser_session(request)
        identity = auth.resolve(token)
        return {
            **identity,
            "csrf_token": csrf_token(token),
            "capabilities": {
                "voice": False,
                "memory": True,
                "memory_extraction": memory_worker_enabled,
                "online_reminders": True,
                "canon_update": False,
            },
        }

    @router.post("/auth/logout")
    def logout(request: Request, response: Response):
        token = browser_session(request)
        auth.resolve(token)
        check_csrf(request, token)
        auth.revoke(token)
        response.delete_cookie(session_cookie_name(settings), path="/")
        return {"status": "ok"}

    @router.post("/auth/password")
    def change_password(body: PasswordChangeInput, request: Request, response: Response):
        token = browser_session(request)
        identity = auth.resolve(token)
        check_csrf(request, token)
        auth.change_password(identity["user_id"], body.current_password, body.new_password)
        response.delete_cookie(session_cookie_name(settings), path="/")
        return {"status": "ok"}

    return router
