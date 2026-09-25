from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select

from afterstory.domain import DomainError
from afterstory.models import (
    CharacterInstance,
    MatterRevision,
    OngoingMatter,
    Reminder,
    ReminderDelivery,
)


class MatterService:
    def __init__(self, sessions, delivery_lease_seconds=60):
        self.sessions = sessions
        self.delivery_lease_seconds = delivery_lease_seconds

    @staticmethod
    def _validate_schedule(time_precision, scheduled_at, timezone_name):
        if time_precision == "instant":
            if not scheduled_at or not scheduled_at.tzinfo or not timezone_name:
                raise DomainError(422, "exact_reminder_time_required")
            try:
                ZoneInfo(timezone_name)
            except ZoneInfoNotFoundError:
                raise DomainError(422, "invalid_reminder_timezone") from None
        elif scheduled_at is not None:
            raise DomainError(422, "imprecise_matter_cannot_schedule_delivery")

    @staticmethod
    def _payload(matter):
        return {
            "matter_type": matter.matter_type,
            "status": matter.status,
            "content": matter.content,
            "next_step": matter.next_step,
            "time_precision": matter.time_precision,
            "scheduled_at": matter.scheduled_at.isoformat() if matter.scheduled_at else None,
            "timezone_name": matter.timezone_name,
            "mention_policy": matter.mention_policy,
        }

    @classmethod
    def _append_revision(cls, session, matter, operation):
        session.add(
            MatterRevision(
                matter_id=matter.id,
                revision=matter.revision,
                operation=operation,
                payload=cls._payload(matter),
            )
        )

    @staticmethod
    def _schedule(session, matter):
        if matter.time_precision != "instant" or not matter.scheduled_at:
            return
        occurrence_key = f"matter:{matter.id}:schedule:{matter.revision}"
        reminder = Reminder(
            instance_id=matter.instance_id,
            matter_id=matter.id,
            schedule_revision=matter.revision,
            occurrence_key=occurrence_key,
            due_at=matter.scheduled_at,
            timezone_name=matter.timezone_name,
            status="scheduled",
        )
        session.add(reminder)
        session.flush()
        session.add(
            ReminderDelivery(
                reminder_id=reminder.id,
                occurrence_key=occurrence_key,
                channel="in_app",
                status="pending",
                attempts=0,
            )
        )

    @staticmethod
    def _owned_instance(session, user, instance_id):
        instance = session.scalar(
            select(CharacterInstance).where(
                CharacterInstance.id == instance_id, CharacterInstance.user_id == user
            )
        )
        if not instance:
            raise DomainError(404, "instance_not_found")
        return instance

    def create(
        self,
        user,
        instance_id,
        request_id,
        content,
        matter_type="reminder",
        next_step=None,
        time_precision="unknown",
        scheduled_at=None,
        timezone_name=None,
        mention_policy="when_relevant",
    ):
        self._validate_schedule(time_precision, scheduled_at, timezone_name)
        with self.sessions.begin() as session:
            instance = self._owned_instance(session, user, instance_id)
            existing = session.scalar(
                select(OngoingMatter).where(
                    OngoingMatter.instance_id == instance_id,
                    OngoingMatter.request_id == request_id,
                )
            )
            if existing:
                return self._view(existing)
            matter = OngoingMatter(
                instance_id=instance_id,
                request_id=request_id,
                matter_type=matter_type,
                status="open",
                content=content,
                next_step=next_step,
                time_precision=time_precision,
                scheduled_at=scheduled_at,
                timezone_name=timezone_name,
                mention_policy=mention_policy,
                revision=1,
            )
            session.add(matter)
            instance.data_revision += 1
            session.flush()
            self._append_revision(session, matter, "create")
            self._schedule(session, matter)
            return self._view(matter)

    def revise(
        self,
        user,
        matter_id,
        expected_revision,
        operation,
        scheduled_at=None,
        timezone_name=None,
    ):
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            matter, instance = self._owned_matter(session, user, matter_id)
            if matter.revision != expected_revision:
                raise DomainError(409, "matter_revision_conflict")
            if matter.status != "open":
                raise DomainError(409, "matter_closed")
            if operation == "reschedule":
                self._validate_schedule("instant", scheduled_at, timezone_name)
                matter.time_precision = "instant"
                matter.scheduled_at = scheduled_at
                matter.timezone_name = timezone_name
            elif operation in {"complete", "cancel"}:
                matter.status = "completed" if operation == "complete" else "cancelled"
            else:
                raise DomainError(422, "unsupported_matter_operation")
            for reminder in session.scalars(
                select(Reminder).where(
                    Reminder.matter_id == matter.id, Reminder.status == "scheduled"
                )
            ):
                reminder.status = "cancelled"
                delivery = session.scalar(
                    select(ReminderDelivery).where(ReminderDelivery.reminder_id == reminder.id)
                )
                if delivery and delivery.status != "delivered":
                    delivery.status = "cancelled"
                    delivery.lease_token = None
                    delivery.lease_until = None
            matter.revision += 1
            matter.updated_at = now
            instance.data_revision += 1
            self._append_revision(session, matter, operation)
            if operation == "reschedule":
                self._schedule(session, matter)
            return self._view(matter)

    def _owned_matter(self, session, user, matter_id):
        row = session.execute(
            select(OngoingMatter, CharacterInstance)
            .join(CharacterInstance, CharacterInstance.id == OngoingMatter.instance_id)
            .where(OngoingMatter.id == matter_id, CharacterInstance.user_id == user)
            .with_for_update(of=(OngoingMatter, CharacterInstance))
        ).first()
        if not row:
            raise DomainError(404, "matter_not_found")
        return row

    def list(self, user, instance_id):
        with self.sessions() as session:
            self._owned_instance(session, user, instance_id)
            matters = session.scalars(
                select(OngoingMatter)
                .where(OngoingMatter.instance_id == instance_id)
                .order_by(OngoingMatter.updated_at.desc())
            )
            return {"items": [self._view(item) for item in matters]}

    def claim_due(self, user, instance_id, now=None):
        now = now or datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            self._owned_instance(session, user, instance_id)
            row = session.execute(
                select(ReminderDelivery, Reminder, OngoingMatter)
                .join(Reminder, Reminder.id == ReminderDelivery.reminder_id)
                .join(OngoingMatter, OngoingMatter.id == Reminder.matter_id)
                .where(
                    Reminder.instance_id == instance_id,
                    Reminder.status == "scheduled",
                    Reminder.due_at <= now,
                    OngoingMatter.status == "open",
                    or_(
                        ReminderDelivery.status.in_(["pending", "failed"]),
                        (ReminderDelivery.status == "claimed")
                        & (ReminderDelivery.lease_until <= now),
                    ),
                )
                .order_by(Reminder.due_at, Reminder.id)
                .with_for_update(of=ReminderDelivery, skip_locked=True)
                .limit(1)
            ).first()
            if not row:
                return None
            delivery, reminder, matter = row
            delivery.status = "claimed"
            delivery.attempts += 1
            delivery.lease_token = str(uuid4())
            delivery.lease_until = now + timedelta(seconds=self.delivery_lease_seconds)
            return {
                "delivery_id": delivery.id,
                "lease_token": delivery.lease_token,
                "occurrence_key": delivery.occurrence_key,
                "matter_id": matter.id,
                "content": matter.content,
                "due_at": reminder.due_at,
                "timezone_name": reminder.timezone_name,
            }

    def acknowledge(self, user, delivery_id, lease_token, delivered, error_code=None):
        with self.sessions.begin() as session:
            delivery = session.scalar(
                select(ReminderDelivery)
                .join(Reminder)
                .join(CharacterInstance, CharacterInstance.id == Reminder.instance_id)
                .where(
                    ReminderDelivery.id == delivery_id,
                    CharacterInstance.user_id == user,
                )
                .with_for_update(of=ReminderDelivery)
            )
            if not delivery or delivery.status != "claimed" or delivery.lease_token != lease_token:
                raise DomainError(409, "delivery_lease_superseded")
            delivery.status = "delivered" if delivered else "failed"
            delivery.delivered_at = datetime.now(timezone.utc) if delivered else None
            delivery.error_code = None if delivered else (error_code or "delivery_failed")
            delivery.lease_token = None
            delivery.lease_until = None
            if delivered:
                reminder = session.get(Reminder, delivery.reminder_id)
                reminder.status = "delivered"
            return {"delivery_id": delivery.id, "status": delivery.status}

    @classmethod
    def _view(cls, matter):
        return {"matter_id": matter.id, "revision": matter.revision, **cls._payload(matter)}
