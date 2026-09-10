from afterstory.domain import CharacterResponse, DomainError, ProviderError, TextProvider
from afterstory.repository import Repository


class ConversationService:
    def __init__(self, repository: Repository, provider: TextProvider):
        self.repository = repository
        self.provider = provider

    def send(self, user, conversation_id, request_id, text):
        reservation = self.repository.begin_turn(user, conversation_id, request_id, text)
        if isinstance(reservation, CharacterResponse):
            return reservation
        turn_id, attempt, messages = reservation
        try:
            reply = self.provider.generate(messages)
            if not isinstance(reply, str) or not reply.strip():
                raise ProviderError("llm_empty_response")
        except Exception as exc:
            code = str(exc) if isinstance(exc, ProviderError) else "llm_unexpected_error"
            self.repository.finish_turn(user, conversation_id, turn_id, attempt, error=code)
            raise DomainError(502, code) from None
        return self.repository.finish_turn(user, conversation_id, turn_id, attempt, text=reply)
