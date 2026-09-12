import json
from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy import select, update

from afterstory.domain import DomainError
from afterstory.models import (
    CharacterInstance,
    CharacterState,
    Conversation,
    Relationship,
    StateEvent,
    Turn,
)


def _clean(value):
    value = value.strip() if isinstance(value, str) else None
    return value or None


class StateService:
    """Internal persistence boundary; no policy here invents state changes."""

    def __init__(self, sessions):
        self.sessions = sessions

    @staticmethod
    def _instance(session, user, instance_id):
        instance = session.scalar(
            select(CharacterInstance)
            .where(
                CharacterInstance.id == instance_id,
                CharacterInstance.user_id == user,
            )
            .with_for_update()
        )
        if not instance:
            raise DomainError(404, "instance_not_found")
        return instance

    @staticmethod
    def _event_view(session, event):
        return {
            "event_id": event.id,
            "instance_id": event.instance_id,
            "source_turn_id": event.source_turn_id,
            "revision": event.revision,
            "status": event.status,
            "reason": event.reason,
            "state": event.short_term_state,
            "relationship": {
                "familiarity": event.familiarity,
                "trust": event.trust,
                "closeness": event.closeness,
            },
        }

    @staticmethod
    def _source(session, instance, source_turn_id):
        turn = session.scalar(
            select(Turn)
            .join(Conversation)
            .where(
                Turn.id == source_turn_id,
                Conversation.instance_id == instance.id,
                Turn.status == "completed",
            )
        )
        if not turn:
            raise DomainError(404, "state_source_not_found")
        if turn.context_revision < instance.history_floor_revision:
            raise DomainError(409, "state_source_stale")
        return turn

    def commit(
        self,
        user,
        instance_id,
        request_id,
        source_turn_id,
        expected_revision,
        *,
        short_term_state=None,
        familiarity=None,
        trust=None,
        closeness=None,
        reason,
    ):
        values = {
            "short_term_state": _clean(short_term_state),
            "familiarity": _clean(familiarity),
            "trust": _clean(trust),
            "closeness": _clean(closeness),
            "reason": _clean(reason),
        }
        if not request_id or len(request_id) > 100 or not values["reason"]:
            raise DomainError(422, "invalid_state_event")
        digest = sha256(
            json.dumps(
                {"source_turn_id": source_turn_id, **values},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        with self.sessions.begin() as session:
            instance = self._instance(session, user, instance_id)
            existing = session.scalar(
                select(StateEvent).where(
                    StateEvent.instance_id == instance_id,
                    StateEvent.request_id == request_id,
                )
            )
            if existing:
                if existing.payload_hash != digest:
                    raise DomainError(409, "state_request_conflict")
                return self._event_view(session, existing)
            self._source(session, instance, source_turn_id)
            if session.scalar(
                select(StateEvent).where(
                    StateEvent.instance_id == instance_id,
                    StateEvent.source_turn_id == source_turn_id,
                )
            ):
                raise DomainError(409, "state_source_already_used")
            if instance.dynamics_revision != expected_revision:
                raise DomainError(409, "state_revision_conflict")

            instance.dynamics_revision += 1
            instance.context_revision += 1
            revision = instance.dynamics_revision
            now = datetime.now(timezone.utc)
            state = session.get(CharacterState, instance_id)
            if not state:
                state = CharacterState(instance_id=instance_id)
                session.add(state)
            state.revision = revision
            state.description = values["short_term_state"]
            state.source_turn_id = source_turn_id
            state.updated_at = now
            relationship = session.get(Relationship, instance_id)
            if not relationship:
                relationship = Relationship(instance_id=instance_id)
                session.add(relationship)
            relationship.revision = revision
            relationship.familiarity = values["familiarity"]
            relationship.trust = values["trust"]
            relationship.closeness = values["closeness"]
            relationship.source_turn_id = source_turn_id
            relationship.updated_at = now
            event = StateEvent(
                instance_id=instance_id,
                request_id=request_id,
                payload_hash=digest,
                source_turn_id=source_turn_id,
                revision=revision,
                short_term_state=values["short_term_state"],
                familiarity=values["familiarity"],
                trust=values["trust"],
                closeness=values["closeness"],
                reason=values["reason"],
                status="active",
            )
            session.add(event)
            session.flush()
            return self._event_view(session, event)

    @staticmethod
    def invalidate_for_memory_change(session, instance, now=None):
        state = session.get(CharacterState, instance.id)
        relationship = session.get(Relationship, instance.id)
        active_events = list(
            session.scalars(
                select(StateEvent).where(
                    StateEvent.instance_id == instance.id,
                    StateEvent.status == "active",
                )
            )
        )
        if not state and not relationship and not active_events:
            return
        now = now or datetime.now(timezone.utc)
        instance.dynamics_revision += 1
        if state:
            state.revision = instance.dynamics_revision
            state.description = None
            state.source_turn_id = None
            state.updated_at = now
        if relationship:
            relationship.revision = instance.dynamics_revision
            relationship.familiarity = None
            relationship.trust = None
            relationship.closeness = None
            relationship.source_turn_id = None
            relationship.updated_at = now
        if active_events:
            session.execute(
                update(StateEvent)
                .where(StateEvent.id.in_([event.id for event in active_events]))
                .values(status="excluded", excluded_at=now)
            )
