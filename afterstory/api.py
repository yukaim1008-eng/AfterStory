from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from afterstory.config import Settings
from afterstory.conversation import ConversationService
from afterstory.database import make_sessions
from afterstory.domain import DomainError
from afterstory.memory import MemoryService
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


class MemoryCreateInput(Input):
    request_id: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2000)
    source_message_id: str | None = Field(default=None, min_length=1, max_length=36)


class MemoryUpdateInput(Input):
    expected_revision: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=2000)


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
    memory_service = MemoryService(sessions)

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
    router = APIRouter()

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"error": exc.code})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(status_code=503, content={"error": "database_unavailable"})

    @router.get("/health")
    def health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "model_profile": settings.llm_active_model,
            "provider": settings.active_model.provider,
            "model": settings.active_model.model,
            "user_id": settings.dev_user_id,
            "capabilities": {
                "voice": False,
                "memory": True,
                "memory_extraction": False,
                "canon_update": False,
            },
        }

    @router.get("/characters")
    def characters():
        return repository.characters()

    @router.post("/instances", status_code=201)
    def instances(body: InstanceInput, user=Depends(current_user)):
        return repository.create_instance(user, body.version_id)

    @router.post("/conversations", status_code=201)
    def conversations(body: ConversationInput, user=Depends(current_user)):
        return repository.create_conversation(user, body.instance_id)

    @router.post("/sessions/open")
    def open_session(body: InstanceInput, user=Depends(current_user)):
        return repository.open_session(user, body.version_id)

    @router.get("/conversations")
    def list_conversations(user=Depends(current_user)):
        return repository.conversations(user)

    @router.get("/history")
    def conversation_catalog(
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        user=Depends(current_user),
    ):
        return repository.conversation_catalog(user, offset, limit)

    @router.get("/conversations/{conversation_id}")
    def conversation_info(conversation_id: str, user=Depends(current_user)):
        return repository.conversation_info(user, conversation_id)

    @router.post("/conversations/{conversation_id}/messages")
    def send(conversation_id: str, body: MessageInput, user=Depends(current_user)):
        return service.send(user, conversation_id, body.request_id, body.text)

    @router.get("/conversations/{conversation_id}/messages")
    def history(
        conversation_id: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        around_turn_id: str | None = Query(None, min_length=1, max_length=36),
        user=Depends(current_user),
    ):
        return repository.history(user, conversation_id, offset, limit, around_turn_id)

    @router.get("/instances/{instance_id}/memories")
    def memories(
        instance_id: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        user=Depends(current_user),
    ):
        return memory_service.list(user, instance_id, offset, limit)

    @router.post("/instances/{instance_id}/memories", status_code=201)
    def create_memory(
        instance_id: str,
        body: MemoryCreateInput,
        user=Depends(current_user),
    ):
        return memory_service.create(
            user,
            instance_id,
            body.request_id,
            body.content,
            body.source_message_id,
        )

    @router.patch("/memories/{memory_id}")
    def update_memory(
        memory_id: str,
        body: MemoryUpdateInput,
        user=Depends(current_user),
    ):
        return memory_service.update(
            user, memory_id, body.expected_revision, body.content
        )

    @router.delete("/memories/{memory_id}")
    def delete_memory(
        memory_id: str,
        expected_revision: int = Query(ge=1),
        user=Depends(current_user),
    ):
        return memory_service.delete(user, memory_id, expected_revision)

    app.include_router(router)
    app.include_router(router, prefix="/api")
    return app
