from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from afterstory.api import create_app


def test_memory_and_online_reminder_public_flow_uses_fake_provider(database):
    settings, _ = database
    with TestClient(create_app(settings)) as client:
        instance = client.post("/api/instances", json={"version_id": "test-lan-v1"}).json()
        instance_id = instance["instance_id"]
        memory = client.post(
            f"/api/instances/{instance_id}/memory-operations",
            json={
                "operation_id": "remember-api",
                "action": "remember",
                "content": "用户希望长期聊下去",
            },
        )
        assert memory.status_code == 200
        assert memory.json()["status"] == "committed"
        listed = client.get(f"/api/instances/{instance_id}/memories").json()
        assert listed["items"][0]["memory_type"] == "fact"

        due = datetime.now(timezone.utc) - timedelta(minutes=1)
        matter = client.post(
            f"/api/instances/{instance_id}/matters",
            json={
                "request_id": "matter-api",
                "content": "整理照片",
                "time_precision": "instant",
                "scheduled_at": due.isoformat(),
                "timezone_name": "Asia/Shanghai",
                "mention_policy": "on_due",
            },
        )
        assert matter.status_code == 201
        delivery = client.get(f"/api/instances/{instance_id}/reminder-deliveries/due").json()[
            "delivery"
        ]
        assert delivery["content"] == "整理照片"
        ack = client.post(
            f"/api/reminder-deliveries/{delivery['delivery_id']}/ack",
            json={"lease_token": delivery["lease_token"], "delivered": True},
        )
        assert ack.json()["status"] == "delivered"
