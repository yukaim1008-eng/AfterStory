from datetime import datetime, timezone

from sqlalchemy import select

from afterstory.models import MemoryDependency, MemoryJob


class MemoryLifecycleService:
    INLINE_DEPENDENCY_LIMIT = 100

    @classmethod
    def invalidate_dependents(cls, session, instance, memory):
        now = datetime.now(timezone.utc)
        conditions = [
            MemoryDependency.instance_id == instance.id,
            MemoryDependency.source_type == "memory",
            MemoryDependency.source_id == memory.id,
            MemoryDependency.status == "active",
        ]
        if memory.status == "active":
            conditions.append(MemoryDependency.source_revision < memory.revision)
        dependencies = list(
            session.scalars(
                select(MemoryDependency)
                .where(*conditions)
                .order_by(MemoryDependency.id)
                .limit(cls.INLINE_DEPENDENCY_LIMIT + 1)
                .with_for_update(skip_locked=True)
            )
        )
        for dependency in dependencies[: cls.INLINE_DEPENDENCY_LIMIT]:
            dependency.status = "invalidated"
            dependency.invalidated_at = now
        if len(dependencies) > cls.INLINE_DEPENDENCY_LIMIT:
            job_key = f"memory:{memory.id}:revision:{memory.revision}:rebuild"
            existing = session.scalar(
                select(MemoryJob).where(
                    MemoryJob.instance_id == instance.id,
                    MemoryJob.job_key == job_key,
                )
            )
            if not existing:
                session.add(
                    MemoryJob(
                        instance_id=instance.id,
                        job_key=job_key,
                        job_type="rebuild_dependencies",
                        status="pending",
                        payload={"memory_id": memory.id},
                        target_data_revision=instance.data_revision,
                        attempts=0,
                    )
                )

    @classmethod
    def rebuild_batch(cls, session, job, batch_size=500):
        memory_id = job.payload["memory_id"]
        rows = list(
            session.scalars(
                select(MemoryDependency)
                .where(
                    MemoryDependency.instance_id == job.instance_id,
                    MemoryDependency.source_type == "memory",
                    MemoryDependency.source_id == memory_id,
                    MemoryDependency.status == "active",
                )
                .order_by(MemoryDependency.id)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        now = datetime.now(timezone.utc)
        for dependency in rows:
            dependency.status = "invalidated"
            dependency.invalidated_at = now
        return len(rows) < batch_size
