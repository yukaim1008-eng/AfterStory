from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, StrictStr, field_validator, model_validator

from afterstory.memory_contracts import StrictContract

CONVERSATION_DECISION_SCHEMA_VERSION = "1.0"
CONVERSATION_ORCHESTRATOR_VERSION = "1.0"


def _required(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("text cannot be empty")
    return value


class MemoryCommand(StrictContract):
    action: Literal["remember", "correct", "forget"]
    content: StrictStr | None
    memory_id: StrictStr | None
    expected_revision: int | None = Field(ge=1)

    @field_validator("content", "memory_id")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        return _required(value) if value is not None else None

    @model_validator(mode="after")
    def validate_action(self):
        if self.action == "remember":
            if not self.content or self.memory_id or self.expected_revision is not None:
                raise ValueError("remember requires only content")
        elif self.action == "correct":
            if not self.content or not self.memory_id or self.expected_revision is None:
                raise ValueError("correct requires target, revision and content")
        elif self.content or not self.memory_id or self.expected_revision is None:
            raise ValueError("forget requires target and revision without content")
        return self


class ReminderCommand(StrictContract):
    content: StrictStr
    next_step: StrictStr | None
    time_precision: Literal["instant", "day", "month", "unknown"]
    scheduled_at: datetime | None
    timezone_name: StrictStr | None
    mention_policy: Literal["when_relevant", "on_due", "never"]

    @field_validator("content")
    @classmethod
    def require_content(cls, value: str) -> str:
        return _required(value)

    @field_validator("next_step", "timezone_name")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        return _required(value) if value is not None else None

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.time_precision == "instant":
            if not self.scheduled_at or not self.scheduled_at.tzinfo or not self.timezone_name:
                raise ValueError("instant reminder requires aware time and timezone")
        elif self.scheduled_at is not None:
            raise ValueError("imprecise reminder cannot schedule delivery")
        return self


class StateDraft(StrictContract):
    description: StrictStr
    persistence: Literal["transient", "ongoing", "until_response", "resolved"]
    expression_effect: StrictStr

    @field_validator("description")
    @classmethod
    def require_description(cls, value: str) -> str:
        return _required(value)

    @field_validator("expression_effect")
    @classmethod
    def normalize_effect(cls, value: str) -> str:
        return " ".join(value.split())


class RelationshipEvidenceDraft(StrictContract):
    aspect: Literal["familiarity", "trust", "closeness"]
    direction: Literal["strengthen", "weaken", "neutral"]
    reason: StrictStr
    evidence_kind: Literal["user_explicit", "observed_interaction"]

    @field_validator("reason")
    @classmethod
    def require_reason(cls, value: str) -> str:
        return _required(value)


class RelationshipSnapshotDraft(StrictContract):
    familiarity: StrictStr
    trust: StrictStr
    closeness: StrictStr

    @field_validator("familiarity", "trust", "closeness")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return " ".join(value.split())


class RelationshipDraft(StrictContract):
    evidence: list[RelationshipEvidenceDraft] = Field(min_length=1, max_length=3)
    snapshot: RelationshipSnapshotDraft | None
    reason: StrictStr

    @field_validator("reason")
    @classmethod
    def require_reason(cls, value: str) -> str:
        return _required(value)

    @model_validator(mode="after")
    def unique_aspects(self):
        aspects = [item.aspect for item in self.evidence]
        if len(aspects) != len(set(aspects)):
            raise ValueError("relationship evidence aspects must be unique per turn")
        return self


class ConversationEffects(StrictContract):
    memory_commands: list[MemoryCommand] = Field(max_length=3)
    reminder_commands: list[ReminderCommand] = Field(max_length=3)
    state: StateDraft | None
    relationship: RelationshipDraft | None

    @property
    def has_effects(self) -> bool:
        return bool(
            self.memory_commands
            or self.reminder_commands
            or self.state
            or self.relationship
        )


class ConversationDecision(StrictContract):
    schema_version: Literal["1.0"]
    reply: StrictStr
    intent_labels: list[
        Literal[
            "chat",
            "remember",
            "correct_memory",
            "forget_memory",
            "set_reminder",
            "state_change",
            "relationship_signal",
        ]
    ] = Field(max_length=7)
    memory_commands: list[MemoryCommand] = Field(max_length=3)
    reminder_commands: list[ReminderCommand] = Field(max_length=3)
    state: StateDraft | None
    relationship: RelationshipDraft | None

    @field_validator("reply")
    @classmethod
    def require_reply(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reply cannot be empty")
        return value

    @field_validator("intent_labels")
    @classmethod
    def unique_intents(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("intent labels must be unique")
        return values

    def effects(self) -> ConversationEffects:
        return ConversationEffects(
            memory_commands=self.memory_commands,
            reminder_commands=self.reminder_commands,
            state=self.state,
            relationship=self.relationship,
        )

    @classmethod
    def reply_only(cls, reply: str) -> ConversationDecision:
        return cls(
            schema_version=CONVERSATION_DECISION_SCHEMA_VERSION,
            reply=reply,
            intent_labels=["chat"],
            memory_commands=[],
            reminder_commands=[],
            state=None,
            relationship=None,
        )
