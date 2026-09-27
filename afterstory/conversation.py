from dataclasses import replace
from datetime import datetime, timezone

from afterstory.conversation_provider import ConversationDecisionProvider
from afterstory.domain import CharacterResponse, DomainError, ProviderError, TextProvider
from afterstory.repository import Repository


class ConversationService:
    UNCONFIRMED_OPERATION_REPLY = (
        "我收到了你的请求，但这次操作还没有确认完成。请再试一次，或换一种更明确的说法。"
    )

    def __init__(self, repository: Repository, provider: TextProvider, effect_service=None):
        self.repository = repository
        self.provider = (
            provider
            if hasattr(provider, "generate_turn")
            else ConversationDecisionProvider(provider)
        )
        self.effect_service = effect_service

    def _with_effects(self, user, conversation_id, response):
        if not self.effect_service:
            return response
        response = replace(
            response,
            effects=tuple(self.effect_service.results_for_turn(response.turn_id)),
        )
        provisional, expected, committed = self.effect_service.reply_status_for_turn(
            response.turn_id
        )
        if not expected:
            return response
        text = provisional if committed and provisional else self.UNCONFIRMED_OPERATION_REPLY
        if text != response.text:
            self.repository.replace_assistant_text(
                user,
                conversation_id,
                response.turn_id,
                response.message_id,
                text,
            )
            response = replace(response, text=text)
        return response

    def send(
        self,
        user,
        conversation_id,
        request_id,
        text,
        timezone_name="UTC",
        timezone_source="server_default",
    ):
        for attempt_index in range(2):
            prepared = self.repository.prepare_context(user, conversation_id, text)
            try:
                reservation = self.repository.reserve_turn(
                    user,
                    conversation_id,
                    request_id,
                    text,
                    prepared,
                    timezone_name=timezone_name,
                    timezone_source=timezone_source,
                )
                break
            except DomainError as exc:
                if exc.code != "context_changed_during_prepare" or attempt_index:
                    raise
        if isinstance(reservation, CharacterResponse):
            if self.effect_service:
                self.effect_service.run_turn(reservation.turn_id)
            return self._with_effects(user, conversation_id, reservation)
        turn_id, attempt, messages = reservation
        try:
            decision = self.provider.generate_turn(
                messages,
                datetime.now(timezone.utc),
                timezone_name,
            )
            if not isinstance(decision.reply, str) or not decision.reply.strip():
                raise ProviderError("llm_empty_response")
        except Exception as exc:
            code = str(exc) if isinstance(exc, ProviderError) else "llm_unexpected_error"
            self.repository.finish_turn(user, conversation_id, turn_id, attempt, error=code)
            raise DomainError(502, code) from None
        effects = decision.effects()
        response = self.repository.finish_turn(
            user,
            conversation_id,
            turn_id,
            attempt,
            text=decision.reply,
            effects=effects.model_dump(mode="json") if effects.has_effects else None,
        )
        if self.effect_service and effects.has_effects:
            self.effect_service.run_turn(turn_id)
        if effects.has_effects and not self.effect_service:
            response = self.repository.replace_assistant_text(
                user,
                conversation_id,
                response.turn_id,
                response.message_id,
                self.UNCONFIRMED_OPERATION_REPLY,
            )
        return self._with_effects(user, conversation_id, response)
