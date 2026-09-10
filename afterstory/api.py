from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from afterstory.config import Settings
from afterstory.conversation import ConversationService
from afterstory.database import make_sessions
from afterstory.domain import DomainError
from afterstory.providers import ChatCompletionsProvider, FakeProvider
from afterstory.repository import Repository


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InstanceInput(Input):
    version_id: str = Field(min_length=1, max_length=64)


class ConversationInput(Input):
    instance_id: str = Field(min_length=1, max_length=36)


class MessageInput(Input):
    request_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=8000)


def current_user(request: Request):
    # Local-only M1 identity, never a user-controlled header or JSON field.
    return request.app.state.settings.dev_user_id


def create_app(settings=None, provider=None):
    settings = settings or Settings()
    engine, sessions = make_sessions(settings)
    repository = Repository(sessions, settings.turn_lease_seconds, settings.history_turns)
    provider = provider or (
        FakeProvider()
        if settings.active_model.provider == "fake"
        else ChatCompletionsProvider(settings)
    )
    service = ConversationService(repository, provider)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )
    app.state.settings = settings
    app.state.repository = repository

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"error": exc.code})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={"error": "database_unavailable"})

    @app.get("/health")
    def health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "model_profile": settings.llm_active_model,
            "provider": settings.active_model.provider,
            "model": settings.active_model.model,
        }

    @app.get("/characters")
    def characters():
        return repository.characters()

    @app.post("/instances", status_code=201)
    def instances(body: InstanceInput, user=Depends(current_user)):
        return repository.create_instance(user, body.version_id)

    @app.post("/conversations", status_code=201)
    def conversations(body: ConversationInput, user=Depends(current_user)):
        return repository.create_conversation(user, body.instance_id)

    @app.post("/conversations/{conversation_id}/messages")
    def send(conversation_id: str, body: MessageInput, user=Depends(current_user)):
        return service.send(user, conversation_id, body.request_id, body.text)

    @app.get("/conversations/{conversation_id}/messages")
    def history(
        conversation_id: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        user=Depends(current_user),
    ):
        return repository.history(user, conversation_id, offset, limit)

    return app
