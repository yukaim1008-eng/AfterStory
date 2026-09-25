import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from afterstory.config import Settings
from afterstory.context import ContextAssembler
from afterstory.conversation import ConversationService
from afterstory.database import make_sessions
from afterstory.domain import DomainError
from afterstory.memory import MemoryService
from afterstory.memory_automation import ExplicitMemoryOperationService
from afterstory.providers import ChatCompletionsProvider, FakeProvider
from afterstory.reminders import MatterService
from afterstory.repository import Repository

http_log = logging.getLogger("afterstory.http")
request_id_pattern = re.compile(r"[A-Za-z0-9._-]{1,64}")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InstanceInput(Input):
    version_id: str = Field(min_length=1, max_length=64)


class ConversationInput(Input):
    instance_id: str = Field(min_length=1, max_length=36)


class MessageInput(Input):
    request_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=8000)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)


class MemoryCreateInput(Input):
    request_id: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2000)
    source_message_id: str | None = Field(default=None, min_length=1, max_length=36)


class MemoryUpdateInput(Input):
    expected_revision: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=2000)


class MemoryOperationInput(Input):
    operation_id: str = Field(min_length=1, max_length=100)
    action: str = Field(pattern="^(remember|correct|forget)$")
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    memory_id: str | None = Field(default=None, min_length=1, max_length=36)
    expected_revision: int | None = Field(default=None, ge=1)


class MatterCreateInput(Input):
    request_id: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2000)
    matter_type: str = Field(default="reminder", pattern="^(reminder|commitment|follow_up)$")
    next_step: str | None = Field(default=None, max_length=2000)
    time_precision: str = Field(default="unknown", pattern="^(instant|day|month|unknown)$")
    scheduled_at: datetime | None = None
    timezone_name: str | None = Field(default=None, max_length=64)
    mention_policy: str = Field(default="when_relevant", pattern="^(when_relevant|on_due|never)$")


class MatterReviseInput(Input):
    expected_revision: int = Field(ge=1)
    operation: str = Field(pattern="^(reschedule|complete|cancel)$")
    scheduled_at: datetime | None = None
    timezone_name: str | None = Field(default=None, max_length=64)


class DeliveryAckInput(Input):
    lease_token: str = Field(min_length=1, max_length=36)
    delivered: bool
    error_code: str | None = Field(default=None, max_length=80)


def current_user(request: Request):
    # Local-only M1 identity, never a user-controlled header or JSON field.
    return request.app.state.settings.dev_user_id


def create_app(settings=None, provider=None):
    settings = settings or Settings()
    engine, sessions = make_sessions(settings)
    context = ContextAssembler(
        settings.history_turns,
        settings.memory_context_items,
        settings.memory_context_chars,
    )
    repository = Repository(sessions, settings.turn_lease_seconds, settings.history_turns, context)
    provider = provider or (
        FakeProvider()
        if settings.active_model.provider == "fake"
        else ChatCompletionsProvider(settings)
    )
    service = ConversationService(repository, provider)
    memory_service = MemoryService(sessions)
    operation_service = ExplicitMemoryOperationService(sessions)
    matter_service = MatterService(sessions)

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

    @app.middleware("http")
    async def correlate_request(request, call_next):
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if request_id_pattern.fullmatch(supplied) else str(uuid4())
        request.state.request_id = request_id
        started = perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            route = request.scope.get("route")
            route_path = getattr(route, "path", "unmatched")
            http_log.info(
                "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%s",
                request_id,
                request.method,
                route_path,
                status,
                round((perf_counter() - started) * 1000),
            )

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        http_log.info(
            "request_domain_error request_id=%s status=%s error=%s",
            request.state.request_id,
            exc.status,
            exc.code,
        )
        return JSONResponse(status_code=exc.status, content={"error": exc.code})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        http_log.warning(
            "request_database_error request_id=%s error=database_unavailable",
            request.state.request_id,
        )
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
        return service.send(
            user,
            conversation_id,
            body.request_id,
            body.text,
            timezone_name=body.timezone or settings.user_timezone,
            timezone_source="client_reported" if body.timezone else "server_default",
        )

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
        return memory_service.update(user, memory_id, body.expected_revision, body.content)

    @router.delete("/memories/{memory_id}")
    def delete_memory(
        memory_id: str,
        expected_revision: int = Query(ge=1),
        user=Depends(current_user),
    ):
        return memory_service.delete(user, memory_id, expected_revision)

    @router.post("/instances/{instance_id}/memory-operations")
    def memory_operation(
        instance_id: str,
        body: MemoryOperationInput,
        user=Depends(current_user),
    ):
        if body.action == "remember" and not body.content:
            raise DomainError(422, "memory_content_required")
        if body.action in {"correct", "forget"} and (
            not body.memory_id or body.expected_revision is None
        ):
            raise DomainError(422, "memory_target_required")
        return operation_service.execute(
            user,
            instance_id,
            body.operation_id,
            body.action,
            body.content,
            body.memory_id,
            body.expected_revision,
        )

    @router.get("/instances/{instance_id}/matters")
    def matters(instance_id: str, user=Depends(current_user)):
        return matter_service.list(user, instance_id)

    @router.post("/instances/{instance_id}/matters", status_code=201)
    def create_matter(
        instance_id: str,
        body: MatterCreateInput,
        user=Depends(current_user),
    ):
        return matter_service.create(
            user,
            instance_id,
            body.request_id,
            body.content,
            body.matter_type,
            body.next_step,
            body.time_precision,
            body.scheduled_at,
            body.timezone_name,
            body.mention_policy,
        )

    @router.patch("/matters/{matter_id}")
    def revise_matter(
        matter_id: str,
        body: MatterReviseInput,
        user=Depends(current_user),
    ):
        return matter_service.revise(
            user,
            matter_id,
            body.expected_revision,
            body.operation,
            body.scheduled_at,
            body.timezone_name,
        )

    @router.get("/instances/{instance_id}/reminder-deliveries/due")
    def due_reminder(instance_id: str, user=Depends(current_user)):
        return {"delivery": matter_service.claim_due(user, instance_id)}

    @router.post("/reminder-deliveries/{delivery_id}/ack")
    def acknowledge_reminder(
        delivery_id: str,
        body: DeliveryAckInput,
        user=Depends(current_user),
    ):
        return matter_service.acknowledge(
            user, delivery_id, body.lease_token, body.delivered, body.error_code
        )

    app.include_router(router)
    app.include_router(router, prefix="/api")
    return app
