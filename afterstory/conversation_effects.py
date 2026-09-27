import json
import logging

from pydantic import ValidationError
from sqlalchemy import select

from afterstory.conversation_contracts import ConversationEffects
from afterstory.domain import DomainError
from afterstory.evolution import RelationshipEvolutionService, StateEvolutionService
from afterstory.memory_automation import ExplicitMemoryOperationService
from afterstory.memory_contracts import StateProposal
from afterstory.memory_jobs import MemoryJobService
from afterstory.models import (
    CharacterInstance,
    Conversation,
    MemoryJob,
    Message,
    RelationshipEvidence,
    Turn,
)
from afterstory.reminders import MatterService

log = logging.getLogger("afterstory.conversation_effects")


class ConversationEffectService:
    JOB_TYPE = "conversation_effects"

    def __init__(self, sessions, lease_seconds=120):
        self.sessions = sessions
        self.jobs = MemoryJobService(sessions, lease_seconds)
        self.memories = ExplicitMemoryOperationService(sessions)
        self.matters = MatterService(sessions)
        self.states = StateEvolutionService(sessions)
        self.relationships = RelationshipEvolutionService(sessions)

    @staticmethod
    def job_key(turn_id):
        return f"turn:{turn_id}:conversation_effects"

    def run_turn(self, turn_id):
        with self.sessions() as session:
            row = session.execute(
                select(Turn, Conversation)
                .join(Conversation, Conversation.id == Turn.conversation_id)
                .where(Turn.id == turn_id)
            ).first()
            if not row:
                return []
            turn, conversation = row
            instance_id = conversation.instance_id
        claim = self.jobs.claim_key(instance_id, self.job_key(turn_id), self.JOB_TYPE)
        if not claim:
            return self.results_for_turn(turn_id)
        try:
            payload = self.apply_claim(claim)
            self.jobs.complete_with_payload(claim["job_id"], claim["lease_token"], payload)
        except Exception:
            self.jobs.fail(
                claim["job_id"],
                claim["lease_token"],
                "conversation_effect_processing_failed",
                retry=True,
            )
            log.warning("conversation_effect_processing_failed")
        return self.results_for_turn(turn_id)

    def apply_claim(self, claim):
        try:
            effects = ConversationEffects.model_validate_json(
                json.dumps(claim["payload"]["effects"], ensure_ascii=False)
            )
        except (KeyError, ValidationError, TypeError):
            raise ValueError("invalid_conversation_effect_payload") from None
        with self.sessions() as session:
            row = session.execute(
                select(Turn, Conversation, CharacterInstance, Message)
                .join(Conversation, Conversation.id == Turn.conversation_id)
                .join(CharacterInstance, CharacterInstance.id == Conversation.instance_id)
                .join(Message, Message.turn_id == Turn.id)
                .where(
                    Turn.id == claim["payload"]["turn_id"],
                    Turn.status == "completed",
                    Message.role == "user",
                )
            ).first()
            if not row:
                raise ValueError("conversation_effect_source_missing")
            turn, _, instance, user_message = row
            user = instance.user_id
            instance_id = instance.id

        results = []
        destructive_memory_change = any(
            item.action in {"correct", "forget"} for item in effects.memory_commands
        )
        for index, command in enumerate(effects.memory_commands):
            operation_id = f"conversation:{turn.id}:memory:{index}"
            try:
                receipt = self.memories.execute(
                    user,
                    instance_id,
                    operation_id,
                    command.action,
                    command.content,
                    command.memory_id,
                    command.expected_revision,
                    user_message.id,
                )
                results.append(
                    {
                        "effect": "memory",
                        "action": command.action,
                        "status": receipt["status"],
                        "target_id": receipt["memory_id"],
                        "revision": receipt["revision"],
                        "error_code": None,
                    }
                )
            except DomainError as exc:
                results.append(self._failed("memory", command.action, exc.code))

        for index, command in enumerate(effects.reminder_commands):
            request_id = f"conversation:{turn.id}:matter:{index}"
            try:
                matter = self.matters.create(
                    user,
                    instance_id,
                    request_id,
                    command.content,
                    "reminder",
                    command.next_step,
                    command.time_precision,
                    command.scheduled_at,
                    command.timezone_name,
                    command.mention_policy,
                )
                results.append(
                    {
                        "effect": "matter",
                        "action": "set_reminder",
                        "status": "committed",
                        "target_id": matter["matter_id"],
                        "revision": matter["revision"],
                        "error_code": None,
                    }
                )
            except DomainError as exc:
                results.append(self._failed("matter", "set_reminder", exc.code))

        if effects.state:
            if destructive_memory_change:
                results.append(
                    {
                        "effect": "state",
                        "action": "update",
                        "status": "skipped",
                        "target_id": None,
                        "revision": None,
                        "error_code": "context_reset_by_memory_change",
                    }
                )
            else:
                try:
                    event_id = self.states.apply(
                        user,
                        instance_id,
                        f"conversation:{turn.id}:state",
                        StateProposal(
                            description=effects.state.description,
                            persistence=effects.state.persistence,
                            expression_effect=effects.state.expression_effect,
                            source_turn_ids=[turn.id],
                        ),
                    )
                    results.append(
                        {
                            "effect": "state",
                            "action": "update",
                            "status": "committed",
                            "target_id": event_id,
                            "revision": None,
                            "error_code": None,
                        }
                    )
                except DomainError as exc:
                    results.append(self._failed("state", "update", exc.code))

        if effects.relationship:
            if destructive_memory_change:
                results.append(
                    {
                        "effect": "relationship",
                        "action": "record",
                        "status": "skipped",
                        "target_id": None,
                        "revision": None,
                        "error_code": "context_reset_by_memory_change",
                    }
                )
            else:
                results.extend(
                    self._apply_relationship(user, instance_id, turn.id, effects.relationship)
                )

        return {**claim["payload"], "results": results}

    def _apply_relationship(self, user, instance_id, turn_id, proposal):
        results = []
        already_applied = False
        for item in proposal.evidence:
            try:
                evidence_id = self.relationships.record(
                    user,
                    instance_id,
                    turn_id,
                    item.aspect,
                    item.direction,
                    item.reason,
                    item.evidence_kind,
                )
                with self.sessions() as session:
                    evidence = session.get(RelationshipEvidence, evidence_id)
                    already_applied = already_applied or evidence.status == "applied"
                results.append(
                    {
                        "effect": "relationship",
                        "action": f"record_{item.aspect}",
                        "status": "committed",
                        "target_id": evidence_id,
                        "revision": None,
                        "error_code": None,
                    }
                )
            except DomainError as exc:
                results.append(
                    self._failed("relationship", f"record_{item.aspect}", exc.code)
                )
        if proposal.snapshot and not already_applied:
            with self.sessions() as session:
                expected_revision = session.get(CharacterInstance, instance_id).dynamics_revision
            try:
                revision_id = self.relationships.evaluate(
                    user,
                    instance_id,
                    expected_revision,
                    familiarity=proposal.snapshot.familiarity or None,
                    trust=proposal.snapshot.trust or None,
                    closeness=proposal.snapshot.closeness or None,
                    reason=proposal.reason,
                )
                results.append(
                    {
                        "effect": "relationship",
                        "action": "evaluate",
                        "status": "committed" if revision_id else "deferred",
                        "target_id": revision_id,
                        "revision": None,
                        "error_code": None,
                    }
                )
            except DomainError as exc:
                results.append(self._failed("relationship", "evaluate", exc.code))
        return results

    def results_for_turn(self, turn_id):
        with self.sessions() as session:
            job = session.scalar(
                select(MemoryJob).where(MemoryJob.job_key == self.job_key(turn_id))
            )
            if not job:
                return []
            results = job.payload.get("results") if isinstance(job.payload, dict) else None
            if isinstance(results, list):
                return results
            return [
                {
                    "effect": "orchestration",
                    "action": "apply",
                    "status": job.status,
                    "target_id": None,
                    "revision": None,
                    "error_code": job.error_code,
                }
            ]

    def reply_status_for_turn(self, turn_id):
        with self.sessions() as session:
            job = session.scalar(
                select(MemoryJob).where(MemoryJob.job_key == self.job_key(turn_id))
            )
            if not job or not isinstance(job.payload, dict):
                return None, 0, False
            effects = job.payload.get("effects")
            if not isinstance(effects, dict):
                return None, 0, False
            expected = len(effects.get("memory_commands") or []) + len(
                effects.get("reminder_commands") or []
            )
            provisional = job.payload.get("provisional_reply")
            results = job.payload.get("results")
            committed = (
                [
                    item
                    for item in results
                    if isinstance(item, dict) and item.get("effect") in {"memory", "matter"}
                ]
                if isinstance(results, list)
                else []
            )
            return (
                provisional if isinstance(provisional, str) else None,
                expected,
                expected > 0
                and len(committed) == expected
                and all(item.get("status") == "committed" for item in committed),
            )

    @staticmethod
    def _failed(effect, action, code):
        return {
            "effect": effect,
            "action": action,
            "status": "failed",
            "target_id": None,
            "revision": None,
            "error_code": code,
        }
