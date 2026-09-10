from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class CharacterResponse:
    message_id: str
    turn_id: str
    text: str
    audio_status: str = "not_requested"


class TextProvider(Protocol):
    def generate(self, messages: list[ChatMessage]) -> str: ...


class ProviderError(Exception):
    """Sanitized provider failure, safe to expose without upstream response bodies."""


class DomainError(Exception):
    def __init__(self, status: int, code: str):
        self.status = status
        self.code = code
