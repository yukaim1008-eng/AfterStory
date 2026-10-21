from datetime import datetime, timezone

from scripts.evaluate_runtime import resolve_reminder_request


def test_reminder_evaluation_uses_future_local_date():
    prompt, due = resolve_reminder_request(
        {
            "timezone": "Asia/Shanghai",
            "reminder_token": "社区阅读角的钥匙",
            "reminder_days_from_now": 2,
            "reminder_local_hour": 15,
        },
        now=datetime(2026, 10, 21, 16, 0, tzinfo=timezone.utc),
    )
    assert "2026年10月24日15:00" in prompt
    assert due == datetime(2026, 10, 24, 7, 0, tzinfo=timezone.utc)
