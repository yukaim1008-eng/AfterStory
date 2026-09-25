from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

MEMORY_SCHEMA_VERSION = "1.0"
SUMMARY_SCHEMA_VERSION = "1.0"
MEMORY_EXTRACTOR_VERSION = "1.0"
SUMMARY_BUILDER_VERSION = "1.0"
RETRIEVAL_RERANKER_VERSION = "1.0"


def _normalize(value: str) -> str:
    return " ".join(value.split())


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TimeReference(StrictContract):
    precision: Literal["instant", "day", "month", "range", "unknown"]
    start: datetime | None = None
    end: datetime | None = None
    original_text: StrictStr = ""
    timezone: StrictStr = ""
    timezone_source: Literal["server", "client_reported", "user_stated", "unknown"] = "unknown"

    @field_validator("original_text", "timezone")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _normalize(value)

    @model_validator(mode="after")
    def validate_precision(self):
        if self.precision == "unknown" and (self.start or self.end):
            raise ValueError("unknown time cannot have boundaries")
        if self.precision != "unknown" and not self.start:
            raise ValueError("known time requires start")
        if self.precision == "range" and not self.end:
            raise ValueError("range requires end")
        if self.end and self.start and self.end < self.start:
            raise ValueError("time range is reversed")
        return self


class SourceReference(StrictContract):
    message_id: StrictStr
    turn_id: StrictStr
    conversation_id: StrictStr
    role: Literal["user", "assistant"]
    quote: StrictStr = ""

    @field_validator("message_id", "turn_id", "conversation_id")
    @classmethod
    def require_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("source id cannot be empty")
        return value

    @field_validator("quote")
    @classmethod
    def normalize_quote(cls, value: str) -> str:
        return _normalize(value)


class FactPayload(StrictContract):
    kind: Literal["fact", "preference"]
    subject: StrictStr
    attribute: StrictStr
    value: StrictStr
    conditions: StrictStr = ""
    scope: Literal["reality", "afterstory", "game", "hypothetical"] = "reality"
    valid_time: TimeReference = Field(default_factory=lambda: TimeReference(precision="unknown"))

    @field_validator("subject", "attribute", "value")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = _normalize(value)
        if not value:
            raise ValueError("fact fields cannot be empty")
        return value

    @field_validator("conditions")
    @classmethod
    def normalize_conditions(cls, value: str) -> str:
        return _normalize(value)


class EventPayload(StrictContract):
    kind: Literal["event"] = "event"
    title: StrictStr
    participants: list[StrictStr] = Field(default_factory=list, max_length=20)
    scene: Literal["reality", "afterstory", "game", "hypothetical"]
    summary: StrictStr
    outcome: StrictStr = ""
    open_question: StrictStr = ""
    occurred_at: TimeReference = Field(default_factory=lambda: TimeReference(precision="unknown"))

    @field_validator("title", "summary")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = _normalize(value)
        if not value:
            raise ValueError("event fields cannot be empty")
        return value

    @field_validator("outcome", "open_question")
    @classmethod
    def normalize_optional(cls, value: str) -> str:
        return _normalize(value)

    @field_validator("participants")
    @classmethod
    def normalize_participants(cls, values: list[str]) -> list[str]:
        normalized = [_normalize(value) for value in values]
        if any(not value for value in normalized):
            raise ValueError("participant cannot be empty")
        return list(dict.fromkeys(normalized))


MemoryPayload = Annotated[FactPayload | EventPayload, Field(discriminator="kind")]


class MemoryCandidate(StrictContract):
    schema_version: Literal["1.0"] = MEMORY_SCHEMA_VERSION
    evidence: Literal["manual", "user_explicit", "observed_interaction", "inference"]
    importance_reason: StrictStr
    payload: MemoryPayload
    sources: list[SourceReference] = Field(min_length=1, max_length=20)

    @field_validator("importance_reason")
    @classmethod
    def require_reason(cls, value: str) -> str:
        value = _normalize(value)
        if not value:
            raise ValueError("importance reason cannot be empty")
        return value

    @model_validator(mode="after")
    def protect_hypothetical_scope(self):
        if self.payload.scope == "hypothetical" and self.evidence == "user_explicit":
            self.evidence = "inference"
        return self


class MemoryOperationCandidate(StrictContract):
    action: Literal["create", "supplement", "correct", "no_change", "defer"]
    target_memory_id: StrictStr | None = None
    memory: MemoryCandidate | None = None
    reason: StrictStr

    @field_validator("target_memory_id")
    @classmethod
    def normalize_target(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None

    @field_validator("reason")
    @classmethod
    def require_reason(cls, value: str) -> str:
        value = _normalize(value)
        if not value:
            raise ValueError("operation reason cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_action(self):
        if self.action == "create" and (not self.memory or self.target_memory_id):
            raise ValueError("create requires memory and no target")
        if self.action in {"supplement", "correct"} and (
            not self.memory or not self.target_memory_id
        ):
            raise ValueError("update operations require target and memory")
        if self.action in {"no_change", "defer"} and self.memory:
            raise ValueError("non-write operations cannot contain memory")
        return self


class SummaryTopic(StrictContract):
    topic: StrictStr
    development: StrictStr
    conclusion: StrictStr = ""
    unresolved: StrictStr = ""
    source_message_ids: list[StrictStr] = Field(min_length=1, max_length=100)

    @field_validator("topic", "development")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = _normalize(value)
        if not value:
            raise ValueError("summary topic fields cannot be empty")
        return value

    @field_validator("conclusion", "unresolved")
    @classmethod
    def normalize_optional(cls, value: str) -> str:
        return _normalize(value)


class SummaryCandidate(StrictContract):
    schema_version: Literal["1.0"] = SUMMARY_SCHEMA_VERSION
    topics: list[SummaryTopic] = Field(default_factory=list, max_length=50)
    covered_turn_ids: list[StrictStr] = Field(min_length=1, max_length=500)


class RerankCandidate(StrictContract):
    candidate_id: StrictStr
    reason: StrictStr

    @field_validator("candidate_id", "reason")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = _normalize(value)
        if not value:
            raise ValueError("rerank fields cannot be empty")
        return value


class RerankResult(StrictContract):
    items: list[RerankCandidate] = Field(default_factory=list, max_length=100)


class StateProposal(StrictContract):
    description: StrictStr
    persistence: Literal["transient", "ongoing", "until_response", "resolved"]
    expression_effect: StrictStr = ""
    source_turn_ids: list[StrictStr] = Field(min_length=1, max_length=20)

    @field_validator("description")
    @classmethod
    def require_description(cls, value: str) -> str:
        value = _normalize(value)
        if not value:
            raise ValueError("state description cannot be empty")
        return value

    @field_validator("expression_effect")
    @classmethod
    def normalize_effect(cls, value: str) -> str:
        return _normalize(value)


class MemoryExtractionProvider(Protocol):
    def extract(self, messages: list[dict]) -> list[MemoryOperationCandidate]: ...


class SummaryProvider(Protocol):
    def summarize(self, messages: list[dict]) -> SummaryCandidate: ...


class RetrievalReranker(Protocol):
    def rerank(self, query: str, candidates: list[dict]) -> RerankResult: ...


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


class ConservativeTokenCounter:
    def count(self, text: str) -> int:
        if not text:
            return 0
        return max(1, (len(text.encode("utf-8")) + 2) // 3)
