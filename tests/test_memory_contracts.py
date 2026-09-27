import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from afterstory.memory_contracts import (
    ConservativeTokenCounter,
    EventPayload,
    FactPayload,
    MemoryCandidate,
    MemoryOperationCandidate,
    SourceReference,
    SummaryCandidate,
    TimeReference,
)


def source():
    return SourceReference(
        message_id="message-1",
        turn_id="turn-1",
        conversation_id="conversation-1",
        role="user",
        quote="  我   喝咖啡不加糖  ",
    )


def fact_candidate():
    return MemoryCandidate(
        evidence="user_explicit",
        importance_reason="稳定偏好",
        payload=FactPayload(
            kind="preference",
            subject=" 用户 ",
            attribute="咖啡甜度",
            value="不加糖",
        ),
        sources=[source()],
    )


def test_contracts_normalize_and_validate_operations():
    candidate = fact_candidate()
    assert candidate.payload.subject == "用户"
    assert candidate.sources[0].quote == "我 喝咖啡不加糖"
    operation = MemoryOperationCandidate(
        action="create", memory=candidate, reason=" 新增长期偏好 "
    )
    assert operation.reason == "新增长期偏好"
    with pytest.raises(ValidationError):
        MemoryOperationCandidate(
            action="correct", memory=candidate, reason="缺少目标"
        )
    with pytest.raises(ValidationError):
        MemoryOperationCandidate(
            action="no_change", memory=candidate, reason="不应携带内容"
        )


def test_contracts_reject_unknown_fields_and_wrong_types():
    data = fact_candidate().model_dump()
    data["unknown"] = "not allowed"
    with pytest.raises(ValidationError):
        MemoryCandidate.model_validate(data)
    data = fact_candidate().model_dump()
    data["payload"]["value"] = 12
    with pytest.raises(ValidationError):
        MemoryCandidate.model_validate(data)


def test_time_precision_and_event_contract():
    with pytest.raises(ValidationError):
        TimeReference(precision="day")
    with pytest.raises(ValidationError):
        TimeReference(
            precision="unknown",
            start=datetime.fromisoformat("2026-09-20T00:00:00+00:00"),
        )
    event = EventPayload(
        title="排班争执",
        participants=["用户", "小周", "用户"],
        scene="reality",
        summary="双方因为排班发生争执",
        occurred_at=TimeReference(
            precision="day",
            start=datetime.fromisoformat("2026-09-20T00:00:00+08:00"),
            timezone="Asia/Shanghai",
            timezone_source="client_reported",
        ),
    )
    assert event.participants == ["用户", "小周"]
    candidate = MemoryCandidate(
        evidence="user_explicit",
        importance_reason="仅是假设事件",
        payload=EventPayload(
            title="假设旅行",
            scene="hypothetical",
            summary="讨论假如去旅行",
        ),
        sources=[source()],
    )
    assert candidate.evidence == "inference"


def test_summary_requires_covered_turns():
    with pytest.raises(ValidationError):
        SummaryCandidate(covered_turn_ids=[])


def test_evaluation_fixture_covers_required_dimensions():
    path = Path(__file__).parents[1] / "fixtures" / "memory_evaluation.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    categories = {row["category"] for row in rows}
    assert {
        "extraction",
        "abstention",
        "multi_session",
        "knowledge_update",
        "temporal",
        "continuity",
        "reminder",
        "relationship",
        "lifecycle",
    } <= categories
    assert len({row["id"] for row in rows}) == len(rows)


def test_runtime_evaluation_fixture_has_bounded_virtual_users_and_long_history():
    path = Path(__file__).parents[1] / "fixtures" / "runtime_evaluation.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenarios = payload["memory_scenarios"]
    assert payload["schema_version"] == "1.0"
    assert {item["id"] for item in scenarios} == {
        "stable-preference",
        "hypothetical-identity",
        "explicit-correction",
        "event-continuation",
    }
    assert len({item["user_id"] for item in scenarios}) == len(scenarios)
    assert len(payload["long_conversation"]["turns"]) == 20
    assert payload["isolation"]["source_user_id"] != payload["isolation"]["other_user_id"]


def test_conservative_token_counter_is_stable():
    counter = ConservativeTokenCounter()
    assert counter.count("") == 0
    assert counter.count("hello") == counter.count("hello")
    assert counter.count("这是中文") > 0
