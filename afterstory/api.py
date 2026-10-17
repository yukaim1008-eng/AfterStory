import asyncio
import logging
import re
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from afterstory.auth.http import current_user as current_user
from afterstory.auth.routes import build_router as build_auth_router
from afterstory.auth.service import AuthService
from afterstory.character.routes import build_router as build_character_router
from afterstory.config import Settings
from afterstory.conversation.context import ContextAssembler
from afterstory.conversation.effects import ConversationEffectService
from afterstory.conversation.provider import ConversationDecisionProvider
from afterstory.conversation.repository import Repository
from afterstory.conversation.routes import build_router as build_conversation_router
from afterstory.conversation.service import ConversationService
from afterstory.database import make_sessions
from afterstory.domain import DomainError
from afterstory.memory.automation import ExplicitMemoryOperationService
from afterstory.memory.provider import StructuredMemoryProvider
from afterstory.memory.reminders import MatterService
from afterstory.memory.retrieval import RetrievalService
from afterstory.memory.routes import build_router as build_memory_router
from afterstory.memory.service import MemoryService
from afterstory.memory.worker import MemoryRuntimeWorker
from afterstory.providers import ChatCompletionsProvider, FakeProvider

http_log = logging.getLogger("afterstory.http")
request_id_pattern = re.compile(r"[A-Za-z0-9._-]{1,64}")


def create_app(settings=None, provider=None):
    settings = settings or Settings()
    engine, sessions = make_sessions(settings)
    auth = AuthService(sessions)
    context = ContextAssembler(
        settings.history_turns,
        settings.memory_context_items,
        settings.memory_context_chars,
        total_tokens=settings.chat_input_tokens,
        overhead_tokens=settings.chat_context_overhead_tokens,
        character_tokens=settings.character_context_tokens,
        memory_tokens=settings.memory_context_tokens,
        dynamics_tokens=settings.dynamics_context_tokens,
        continuity_tokens=settings.continuity_context_tokens,
        history_tokens=settings.history_context_tokens,
        current_message_tokens=settings.current_message_tokens,
    )
    retrieval = RetrievalService(
        sessions,
        max_items=settings.memory_context_items,
        max_tokens=settings.memory_context_tokens,
    )
    repository = Repository(
        sessions,
        lease_seconds=settings.turn_lease_seconds,
        history_turns=settings.history_turns,
        context=context,
        retrieval=retrieval,
    )
    provider = provider or (
        FakeProvider()
        if settings.active_model.provider == "fake"
        else ChatCompletionsProvider(settings)
    )
    effect_service = ConversationEffectService(sessions, settings.turn_lease_seconds)
    conversation_provider = ConversationDecisionProvider(
        provider, max_tokens=settings.active_model.max_tokens
    )
    service = ConversationService(repository, conversation_provider, effect_service)
    memory_service = MemoryService(sessions)
    operation_service = ExplicitMemoryOperationService(sessions)
    matter_service = MatterService(sessions)

    memory_worker = None
    if settings.active_model.provider != "fake":
        structured_provider = StructuredMemoryProvider(
            provider,
            extraction_input_tokens=settings.memory_extraction_input_tokens,
            extraction_candidate_items=settings.memory_extraction_candidate_items,
            extraction_candidate_tokens=settings.memory_extraction_candidate_tokens,
            summary_input_tokens=settings.summary_input_tokens,
        )
        memory_worker = MemoryRuntimeWorker(
            sessions,
            structured_provider,
            structured_provider,
            settings.turn_lease_seconds,
            extraction_candidate_items=settings.memory_extraction_candidate_items,
            summary_segment_turns=settings.summary_segment_turns,
            summary_source_tokens=settings.summary_source_tokens,
            conversation_effects=effect_service,
        )

    @asynccontextmanager
    async def lifespan(app):
        stop = asyncio.Event()

        async def work():
            while not stop.is_set():
                worked = await asyncio.to_thread(memory_worker.run_once)
                if not worked:
                    try:
                        await asyncio.wait_for(
                            stop.wait(), timeout=settings.memory_worker_poll_seconds
                        )
                    except TimeoutError:
                        pass

        task = asyncio.create_task(work()) if memory_worker else None
        try:
            yield
        finally:
            stop.set()
            if task:
                await task
            engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[host.strip() for host in settings.allowed_hosts.split(",") if host.strip()],
    )
    app.state.settings = settings
    app.state.repository = repository
    app.state.auth = auth
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
        return {"status": "ok"}

    router.include_router(build_auth_router(auth, settings, memory_worker is not None))
    router.include_router(build_character_router(repository))
    router.include_router(build_conversation_router(repository, service, settings))
    router.include_router(build_memory_router(memory_service, operation_service, matter_service))

    app.include_router(router)
    app.include_router(router, prefix="/api")
    return app
