from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from afterstory.domain import DomainError
from afterstory.models import MatterRevision, Reminder, ReminderDelivery
from afterstory.reminders import MatterService
from afterstory.repository import Repository


def test_due_reminder_is_claimed_once_and_acknowledged(database):
    _, sessions = database
    instance_id = Repository(sessions).create_instance("alice", "test-lan-v1")["instance_id"]
    service = MatterService(sessions, delivery_lease_seconds=30)
    due = datetime.now(timezone.utc) - timedelta(minutes=5)
    matter = service.create(
        "alice",
        instance_id,
        "remind",
        "提醒我整理照片",
        time_precision="instant",
        scheduled_at=due,
        timezone_name="Asia/Shanghai",
    )
    claim = service.claim_due("alice", instance_id)
    assert claim["matter_id"] == matter["matter_id"]
    assert service.claim_due("alice", instance_id) is None
    assert (
        service.acknowledge("alice", claim["delivery_id"], claim["lease_token"], True)["status"]
        == "delivered"
    )
    assert service.claim_due("alice", instance_id) is None


def test_reschedule_cancels_old_occurrence_and_vague_time_never_promises_delivery(database):
    _, sessions = database
    instance_id = Repository(sessions).create_instance("alice", "test-lan-v1")["instance_id"]
    service = MatterService(sessions)
    vague = service.create("alice", instance_id, "vague", "下个月整理照片", time_precision="month")
    assert vague["scheduled_at"] is None
    with pytest.raises(DomainError) as error:
        service.create(
            "alice",
            instance_id,
            "bad",
            "时间不够精确",
            time_precision="month",
            scheduled_at=datetime.now(timezone.utc),
            timezone_name="Asia/Shanghai",
        )
    assert error.value.code == "imprecise_matter_cannot_schedule_delivery"

    future = datetime.now(timezone.utc) + timedelta(days=1)
    exact = service.create(
        "alice",
        instance_id,
        "exact",
        "明天提醒",
        time_precision="instant",
        scheduled_at=future,
        timezone_name="Asia/Shanghai",
    )
    revised = service.revise(
        "alice",
        exact["matter_id"],
        1,
        "reschedule",
        future + timedelta(days=1),
        "Asia/Shanghai",
    )
    assert revised["revision"] == 2
    with sessions() as session:
        reminders = list(
            session.scalars(
                select(Reminder)
                .where(Reminder.matter_id == exact["matter_id"])
                .order_by(Reminder.schedule_revision)
            )
        )
        assert [item.status for item in reminders] == ["cancelled", "scheduled"]
        assert session.scalar(select(func.count()).select_from(MatterRevision)) == 3
        deliveries = list(session.scalars(select(ReminderDelivery)))
        assert any(item.status == "cancelled" for item in deliveries)
