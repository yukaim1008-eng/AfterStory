"""Character and instance HTTP routes."""

from fastapi import APIRouter, Depends
from pydantic import Field

from afterstory.api_types import Input
from afterstory.auth.http import current_user


class InstanceInput(Input):
    version_id: str = Field(min_length=1, max_length=64)


def build_router(repository):
    router = APIRouter()

    @router.get("/characters")
    def characters():
        return repository.characters()

    @router.post("/instances", status_code=201)
    def instances(body: InstanceInput, user=Depends(current_user)):
        return repository.create_instance(user, body.version_id)

    return router
