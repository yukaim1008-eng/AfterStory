import logging

from sqlalchemy import select

from afterstory.continuity import ContinuityService
from afterstory.lifecycle import MemoryLifecycleService
from afterstory.memory_automation import MemoryAutomationService
from afterstory.memory_jobs import MemoryJobService
from afterstory.models import MemoryJob

log = logging.getLogger("afterstory.memory_worker")


class MemoryRuntimeWorker:
    def __init__(
        self,
        sessions,
        extraction_provider,
        summary_provider,
        lease_seconds=120,
        *,
        extraction_candidate_items=20,
        summary_segment_turns=20,
        summary_source_tokens=22000,
        conversation_effects=None,
    ):
        self.sessions = sessions
        self.extraction_provider = extraction_provider
        self.summary_provider = summary_provider
        self.extraction_candidate_items = extraction_candidate_items
        self.summary_segment_turns = summary_segment_turns
        self.summary_source_tokens = summary_source_tokens
        self.conversation_effects = conversation_effects
        self.jobs = MemoryJobService(sessions, lease_seconds)

    def run_once(self):
        claim = (
            self.jobs.claim(["conversation_effects"])
            if self.conversation_effects
            else None
        )
        if not claim:
            claim = self.jobs.claim(["extract", "summarize", "rebuild_dependencies"])
        if not claim:
            return False
        try:
            if claim["job_type"] == "extract":
                MemoryAutomationService(
                    self.sessions,
                    self.extraction_provider,
                    self.extraction_candidate_items,
                ).process_turn(
                    claim["payload"]["turn_id"]
                )
            elif claim["job_type"] == "summarize":
                ContinuityService(
                    self.sessions,
                    self.summary_provider,
                    segment_turns=self.summary_segment_turns,
                    max_source_tokens=self.summary_source_tokens,
                ).summarize_next(
                    claim["instance_id"], claim["payload"]["conversation_id"]
                )
            elif claim["job_type"] == "conversation_effects":
                if not self.conversation_effects:
                    raise ValueError("conversation_effect_service_missing")
                payload = self.conversation_effects.apply_claim(claim)
                self.jobs.complete_with_payload(
                    claim["job_id"], claim["lease_token"], payload
                )
                return True
            else:
                with self.sessions.begin() as session:
                    job = session.scalar(
                        select(MemoryJob)
                        .where(
                            MemoryJob.id == claim["job_id"],
                            MemoryJob.lease_token == claim["lease_token"],
                        )
                        .with_for_update()
                    )
                    if not job:
                        return True
                    complete = MemoryLifecycleService.rebuild_batch(session, job)
                if not complete:
                    self.jobs.fail(claim["job_id"], claim["lease_token"], "rebuild_continues", True)
                    return True
            self.jobs.complete(claim["job_id"], claim["lease_token"])
        except Exception as exc:
            retry = self._attempts(claim["job_id"]) < 3
            self.jobs.fail(
                claim["job_id"],
                claim["lease_token"],
                type(exc).__name__[:80],
                retry,
            )
            log.warning(
                "memory_job_failed job_id=%s type=%s retry=%s",
                claim["job_id"],
                claim["job_type"],
                retry,
            )
        return True

    def _attempts(self, job_id):
        with self.sessions() as session:
            job = session.get(MemoryJob, job_id)
            return job.attempts if job else 3
