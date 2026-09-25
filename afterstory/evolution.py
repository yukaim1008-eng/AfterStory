import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from sqlalchemy import select

from afterstory.domain import DomainError
from afterstory.memory_contracts import StateProposal
from afterstory.models import (
    CharacterInstance,
    CharacterState,
    Conversation,
    Relationship,
    RelationshipEvidence,
    RelationshipRevision,
    StateEvent,
    Turn,
)


class StateEvolutionService:
    def __init__(self, sessions):
        self.sessions = sessions

    def apply(self, user, instance_id, request_id, proposal):
        proposal = StateProposal.model_validate(proposal)
        now = datetime.now(timezone.utc)
        valid_until = {
            "transient": now + timedelta(hours=6),
            "until_response": now + timedelta(hours=24),
            "ongoing": None,
            "resolved": now,
        }[proposal.persistence]
        digest = sha256(
            json.dumps(proposal.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        with self.sessions.begin() as session:
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
            existing = session.scalar(
                select(StateEvent).where(
                    StateEvent.instance_id == instance_id,
                    StateEvent.request_id == request_id,
                )
            )
            if existing:
                if existing.payload_hash != digest:
                    raise DomainError(409, "state_request_conflict")
                return existing.id
            turns = list(
                session.scalars(
                    select(Turn)
                    .join(Conversation)
                    .where(
                        Turn.id.in_(proposal.source_turn_ids),
                        Conversation.instance_id == instance_id,
                        Turn.status == "completed",
                        Turn.context_revision >= instance.history_floor_revision,
                    )
                )
            )
            if len(turns) != len(set(proposal.source_turn_ids)):
                raise DomainError(409, "state_source_stale")
            instance.dynamics_revision += 1
            instance.data_revision += 1
            instance.context_revision += 1
            state = session.get(CharacterState, instance_id)
            if not state:
                state = CharacterState(instance_id=instance_id)
                session.add(state)
            state.revision = instance.dynamics_revision
            state.description = None if proposal.persistence == "resolved" else proposal.description
            state.persistence = proposal.persistence
            state.valid_until = valid_until
            state.source_turn_id = proposal.source_turn_ids[-1]
            state.updated_at = now
            event = StateEvent(
                instance_id=instance_id,
                request_id=request_id,
                payload_hash=digest,
                source_turn_id=proposal.source_turn_ids[-1],
                revision=instance.dynamics_revision,
                short_term_state=state.description,
                persistence=proposal.persistence,
                valid_until=valid_until,
                reason=proposal.expression_effect or "state proposal",
                status="active",
            )
            session.add(event)
            session.flush()
            return event.id


class RelationshipEvolutionService:
    ASPECTS = {"familiarity", "trust", "closeness"}
    DIRECTIONS = {"strengthen", "weaken", "neutral"}

    def __init__(self, sessions, minimum_evidence=2):
        self.sessions = sessions
        self.minimum_evidence = minimum_evidence

    def record(self, user, instance_id, source_turn_id, aspect, direction, reason, evidence_kind):
        if aspect not in self.ASPECTS or direction not in self.DIRECTIONS or not reason.strip():
            raise DomainError(422, "invalid_relationship_evidence")
        with self.sessions.begin() as session:
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
            turn = session.scalar(
                select(Turn)
                .join(Conversation)
                .where(
                    Turn.id == source_turn_id,
                    Conversation.instance_id == instance_id,
                    Turn.status == "completed",
                    Turn.context_revision >= instance.history_floor_revision,
                )
            )
            if not turn:
                raise DomainError(409, "relationship_source_stale")
            existing = session.scalar(
                select(RelationshipEvidence).where(
                    RelationshipEvidence.instance_id == instance_id,
                    RelationshipEvidence.source_turn_id == source_turn_id,
                    RelationshipEvidence.aspect == aspect,
                )
            )
            if existing:
                return existing.id
            evidence = RelationshipEvidence(
                instance_id=instance_id,
                source_turn_id=source_turn_id,
                aspect=aspect,
                direction=direction,
                reason=reason.strip(),
                evidence_kind=evidence_kind,
                status="active",
            )
            session.add(evidence)
            instance.data_revision += 1
            session.flush()
            return evidence.id

    def evaluate(
        self,
        user,
        instance_id,
        expected_revision,
        *,
        familiarity=None,
        trust=None,
        closeness=None,
        reason,
    ):
        with self.sessions.begin() as session:
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
            if instance.dynamics_revision != expected_revision:
                raise DomainError(409, "state_revision_conflict")
            evidence = list(
                session.scalars(
                    select(RelationshipEvidence)
                    .where(
                        RelationshipEvidence.instance_id == instance_id,
                        RelationshipEvidence.status == "active",
                        RelationshipEvidence.direction != "neutral",
                    )
                    .order_by(RelationshipEvidence.created_at, RelationshipEvidence.id)
                )
            )
            if len(evidence) < self.minimum_evidence:
                return None
            instance.dynamics_revision += 1
            instance.data_revision += 1
            instance.context_revision += 1
            relationship = session.get(Relationship, instance_id)
            if not relationship:
                relationship = Relationship(instance_id=instance_id)
                session.add(relationship)
            relationship.revision = instance.dynamics_revision
            relationship.familiarity = familiarity
            relationship.trust = trust
            relationship.closeness = closeness
            relationship.source_turn_id = evidence[-1].source_turn_id
            relationship.updated_at = datetime.now(timezone.utc)
            revision = RelationshipRevision(
                instance_id=instance_id,
                revision=instance.dynamics_revision,
                familiarity=familiarity,
                trust=trust,
                closeness=closeness,
                evidence_ids=[item.id for item in evidence],
                reason=reason,
            )
            session.add(revision)
            for item in evidence:
                item.status = "applied"
            session.flush()
            return revision.id
