from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import or_, select

from afterstory.models import MemoryJob


class MemoryJobService:
    """Small PostgreSQL-backed outbox with idempotent keys and recoverable leases."""

    def __init__(self, sessions, lease_seconds=120):
        self.sessions = sessions
        self.lease_seconds = lease_seconds

    def enqueue(self, instance_id, job_key, job_type, payload, target_data_revision):
        with self.sessions.begin() as session:
            existing = session.scalar(
                select(MemoryJob).where(
                    MemoryJob.instance_id == instance_id, MemoryJob.job_key == job_key
                )
            )
            if existing:
                return existing.id
            job = MemoryJob(
                instance_id=instance_id,
                job_key=job_key,
                job_type=job_type,
                status="pending",
                payload=payload,
                target_data_revision=target_data_revision,
                attempts=0,
            )
            session.add(job)
            session.flush()
            return job.id

    def claim(self, job_types=None):
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            query = (
                select(MemoryJob)
                .where(
                    or_(
                        MemoryJob.status == "pending",
                        (MemoryJob.status == "processing") & (MemoryJob.lease_until <= now),
                    )
                )
                .order_by(MemoryJob.created_at, MemoryJob.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job_types:
                query = query.where(MemoryJob.job_type.in_(job_types))
            job = session.scalar(query)
            if not job:
                return None
            job.status = "processing"
            job.attempts += 1
            job.lease_token = str(uuid4())
            job.lease_until = now + timedelta(seconds=self.lease_seconds)
            job.updated_at = now
            session.flush()
            return dict(
                job_id=job.id,
                lease_token=job.lease_token,
                job_type=job.job_type,
                instance_id=job.instance_id,
                payload=job.payload,
                target_data_revision=job.target_data_revision,
            )

    def claim_key(self, instance_id, job_key, job_type):
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            job = session.scalar(
                select(MemoryJob)
                .where(
                    MemoryJob.instance_id == instance_id,
                    MemoryJob.job_key == job_key,
                    MemoryJob.job_type == job_type,
                    or_(
                        MemoryJob.status == "pending",
                        (MemoryJob.status == "processing") & (MemoryJob.lease_until <= now),
                    ),
                )
                .with_for_update(skip_locked=True)
            )
            if not job:
                return None
            job.status = "processing"
            job.attempts += 1
            job.lease_token = str(uuid4())
            job.lease_until = now + timedelta(seconds=self.lease_seconds)
            job.updated_at = now
            session.flush()
            return dict(
                job_id=job.id,
                lease_token=job.lease_token,
                job_type=job.job_type,
                instance_id=job.instance_id,
                payload=job.payload,
                target_data_revision=job.target_data_revision,
            )

    def complete(self, job_id, lease_token):
        return self._finish(job_id, lease_token, "completed", None)

    def complete_with_payload(self, job_id, lease_token, payload):
        with self.sessions.begin() as session:
            job = session.scalar(select(MemoryJob).where(MemoryJob.id == job_id).with_for_update())
            if not job or job.status != "processing" or job.lease_token != lease_token:
                return False
            job.payload = payload
            job.status = "completed"
            job.error_code = None
            job.lease_token = None
            job.lease_until = None
            job.updated_at = datetime.now(timezone.utc)
            return True

    def fail(self, job_id, lease_token, error_code, retry=True):
        return self._finish(job_id, lease_token, "pending" if retry else "failed", error_code)

    def _finish(self, job_id, lease_token, status, error_code):
        with self.sessions.begin() as session:
            job = session.scalar(select(MemoryJob).where(MemoryJob.id == job_id).with_for_update())
            if not job or job.status != "processing" or job.lease_token != lease_token:
                return False
            job.status = status
            job.error_code = error_code
            job.lease_token = None
            job.lease_until = None
            job.updated_at = datetime.now(timezone.utc)
            return True
