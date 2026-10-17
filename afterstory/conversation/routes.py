"""Conversation and history HTTP routes."""

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from afterstory.api_types import Input
from afterstory.auth.http import current_user
from afterstory.character.routes import InstanceInput


class ConversationInput(Input):
    instance_id: str = Field(min_length=1, max_length=36)


class MessageInput(Input):
    request_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=8000)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)


def build_router(repository, service, settings):
    router = APIRouter()

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

    return router
