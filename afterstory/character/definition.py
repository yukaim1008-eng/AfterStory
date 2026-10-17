import re

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator

SUPPORTED_CHARACTER_DEFINITION_SCHEMA_VERSION = "1.0"


class CharacterDefinition(BaseModel):
    """Stable, versioned character material; runtime data belongs to an instance."""

    model_config = ConfigDict(extra="forbid")

    schema_version: StrictStr
    identity: StrictStr
    personality: StrictStr
    speaking_style: StrictStr
    behavior: StrictStr
    worldview: StrictStr
    relationship_premise: StrictStr

    @field_validator(
        "schema_version",
        "identity",
        "personality",
        "speaking_style",
        "behavior",
        "worldview",
        "relationship_premise",
        mode="before",
    )
    @classmethod
    def normalize_whitespace(cls, value):
        if isinstance(value, str):
            return re.sub(r"\s+", " ", value).strip()
        return value

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value):
        if value != SUPPORTED_CHARACTER_DEFINITION_SCHEMA_VERSION:
            raise ValueError("unsupported_character_definition_schema_version")
        return value

    @field_validator("identity")
    @classmethod
    def require_identity(cls, value):
        if not value:
            raise ValueError("identity_required")
        return value
