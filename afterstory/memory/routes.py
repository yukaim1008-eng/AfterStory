"""Memory, matters, and reminder HTTP routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from afterstory.api_types import Input
from afterstory.auth.http import current_user
from afterstory.domain import DomainError


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


def build_router(memory_service, operation_service, matter_service):
    router = APIRouter()

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

    return router
