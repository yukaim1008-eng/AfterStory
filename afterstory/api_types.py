"""Shared strict HTTP input model."""

from pydantic import BaseModel, ConfigDict


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
