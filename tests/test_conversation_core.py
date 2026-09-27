import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from afterstory.api import create_app
from afterstory.context import ContextAssembler
from afterstory.conversation import ConversationService
from afterstory.conversation_contracts import ConversationDecision
from afterstory.conversation_effects import ConversationEffectService
from afterstory.conversation_provider import ConversationDecisionProvider
from afterstory.domain import ChatMessage, ProviderError
from afterstory.memory import MemoryService
from afterstory.memory_contracts import ConservativeTokenCounter
from afterstory.models import (
    CharacterState,
    MemoryJob,
    MemorySourceLink,
    Message,
    OngoingMatter,
    PersonalMemory,
    Relationship,
    RelationshipEvidence,
    RelationshipRevision,
    Reminder,
)
from afterstory.repository import Repository


def decision(**overrides):
    value = {
        "schema_version": "1.0",
        "reply": "我知道了。",
        "intent_labels": ["chat"],
        "memory_commands": [],
        "reminder_commands": [],
        "state": None,
        "relationship": None,
    }
    value.update(overrides)
    return value


class DecisionProvider:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = []
        self.max_tokens = []

    def generate_json(self, messages, max_tokens=None):
        self.calls.append(messages)
        self.max_tokens.append(max_tokens)
        return json.dumps(self.values.pop(0), ensure_ascii=False)


def setup(client):
    instance = client.post("/instances", json={"version_id": "test-lan-v1"}).json()
    conversation = client.post(
        "/conversations", json={"instance_id": instance["instance_id"]}
    ).json()
    return instance["instance_id"], conversation["conversation_id"]


def send(client, conversation_id, request_id, text, timezone_name="Asia/Shanghai"):
    return client.post(
        f"/conversations/{conversation_id}/messages",
        json={"request_id": request_id, "text": text, "timezone": timezone_name},
    )


def test_decision_contract_forbids_unknown_and_invalid_commands():
    with pytest.raises(ValidationError):
        ConversationDecision.model_validate(
            decision(unexpected=True)
        )
    with pytest.raises(ValidationError):
        ConversationDecision.model_validate(
            decision(
                memory_commands=[
                    {
                        "action": "forget",
                        "content": "不应存在",
                        "memory_id": "memory-1",
                        "expected_revision": 1,
                    }
                ]
            )
        )


def test_orchestrator_instruction_fits_reserved_overhead_and_invalid_effects_fall_back():
    now = datetime(2026, 9, 27, tzinfo=timezone.utc)
    instruction = ConversationDecisionProvider._instruction(now, "Asia/Shanghai")
    assert ConservativeTokenCounter().count(instruction) <= 1000

    provider = DecisionProvider(decision(reply="保留这句回复", unexpected=True))
    result = ConversationDecisionProvider(provider).generate_turn(
        [
            type("Message", (), {"role": "system", "content": "角色"})(),
            type("Message", (), {"role": "user", "content": "你好"})(),
        ],
        now,
        "Asia/Shanghai",
    )
    assert result.reply == "保留这句回复"
    assert result.effects().has_effects is False

    normalized = ConversationDecisionProvider._structured_messages(
        [
            ChatMessage("system", "角色"),
            ChatMessage("system", "运行时资料"),
            ChatMessage("user", "上一问"),
            ChatMessage("assistant", "上一答"),
            ChatMessage("user", "当前问题"),
        ],
        now,
        "Asia/Shanghai",
    )
    assert [item.role for item in normalized] == ["system", "user"]
    assert "运行时资料" in normalized[0].content
    payload = json.loads(normalized[1].content)
    assert payload["history"][-1] == {"role": "assistant", "content": "上一答"}
    assert payload["current_user_message"] == "当前问题"

    class EmptyStructuredProvider:
        def generate_json(self, messages, max_tokens=None):
            raise ProviderError("llm_empty_response")

        def generate(self, messages):
            assert "不得声称已经记住" in messages[0].content
            return "这次操作没有完成，请再试一次。"

    result = ConversationDecisionProvider(EmptyStructuredProvider()).generate_turn(
        [ChatMessage("system", "角色"), ChatMessage("user", "请记住这件事")],
        now,
        "Asia/Shanghai",
    )
    assert result.reply == "这次操作没有完成，请再试一次。"
    assert result.effects().has_effects is False

    class OvereagerProvider:
        def generate_json(self, messages, max_tokens=None):
            return json.dumps(
                decision(
                    reply="我记住了。",
                    intent_labels=["remember"],
                    memory_commands=[
                        {
                            "action": "remember",
                            "content": "用户叫林遥",
                            "memory_id": None,
                            "expected_revision": None,
                        }
                    ],
                ),
                ensure_ascii=False,
            )

        def generate(self, messages):
            return "你好，林遥。"

    result = ConversationDecisionProvider(OvereagerProvider()).generate_turn(
        [ChatMessage("system", "角色"), ChatMessage("user", "我叫林遥")],
        now,
        "Asia/Shanghai",
    )
    assert result.reply == "你好，林遥。"
    assert result.effects().has_effects is False

    result = ConversationDecisionProvider(OvereagerProvider()).generate_turn(
        [ChatMessage("system", "角色"), ChatMessage("user", "这件事不要记住")],
        now,
        "Asia/Shanghai",
    )
    assert result.reply == "你好，林遥。"
    assert result.effects().has_effects is False

    class InvisibleTargetProvider:
        def generate_json(self, messages, max_tokens=None):
            return json.dumps(
                decision(
                    reply="已经删掉。",
                    intent_labels=["forget_memory"],
                    memory_commands=[
                        {
                            "action": "forget",
                            "content": None,
                            "memory_id": "not-visible",
                            "expected_revision": 1,
                        }
                    ],
                ),
                ensure_ascii=False,
            )

        def generate(self, messages):
            return "我没有找到可以删除的对应资料。"

    result = ConversationDecisionProvider(InvisibleTargetProvider()).generate_turn(
        [ChatMessage("system", "角色"), ChatMessage("user", "请忘记那条资料")],
        now,
        "Asia/Shanghai",
    )
    assert result.reply == "我没有找到可以删除的对应资料。"
    assert result.effects().has_effects is False


def test_natural_language_remember_is_committed_with_source_and_idempotent(database):
    cfg, sessions = database
    provider = DecisionProvider(
        decision(
            reply="我会记住你喝咖啡不加糖。",
            intent_labels=["remember"],
            memory_commands=[
                {
                    "action": "remember",
                    "content": "用户喝咖啡不加糖",
                    "memory_id": None,
                    "expected_revision": None,
                }
            ],
        )
    )
    with TestClient(create_app(cfg, provider)) as client:
        _, conversation_id = setup(client)
        first = send(client, conversation_id, "remember-one", "请记住，我喝咖啡不加糖")
        assert first.status_code == 200
        assert first.json()["effects"][0]["status"] == "committed"
        duplicate = send(client, conversation_id, "remember-one", "请记住，我喝咖啡不加糖")
        assert duplicate.json() == first.json()
    with sessions() as session:
        memory = session.scalar(select(PersonalMemory))
        assert memory.content == "用户喝咖啡不加糖"
        assert session.scalar(select(func.count()).select_from(PersonalMemory)) == 1
        link = session.scalar(select(MemorySourceLink))
        assert link.source_kind == "message" and link.message_id
        job = session.scalar(
            select(MemoryJob).where(MemoryJob.job_type == "conversation_effects")
        )
        assert job.status == "completed"


def test_correction_and_forget_use_only_visible_memory_identity(database):
    cfg, sessions = database
    repo = Repository(
        sessions,
        context=ContextAssembler(memory_items=20),
    )
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    memory = MemoryService(sessions).create("alice", instance_id, "seed", "我住在杭州")
    provider = DecisionProvider(
        decision(
            reply="已改成苏州。",
            intent_labels=["correct_memory"],
            memory_commands=[
                {
                    "action": "correct",
                    "content": "我住在苏州",
                    "memory_id": memory["memory_id"],
                    "expected_revision": 1,
                }
            ],
        ),
        decision(
            reply="我会忘记这条住址。",
            intent_labels=["forget_memory"],
            memory_commands=[
                {
                    "action": "forget",
                    "content": None,
                    "memory_id": memory["memory_id"],
                    "expected_revision": 2,
                }
            ],
        ),
    )
    effects = ConversationEffectService(sessions)
    service = ConversationService(repo, ConversationDecisionProvider(provider), effects)
    corrected = service.send("alice", conversation_id, "correct", "更正，我一直住在苏州")
    assert corrected.effects[0]["revision"] == 2
    sent = "\n".join(message.content for message in provider.calls[0])
    assert memory["memory_id"] in sent and '"revision":1' in sent
    forgotten = service.send("alice", conversation_id, "forget", "请忘记我的住址")
    assert forgotten.effects[0]["revision"] == 3
    with sessions() as session:
        assert session.get(PersonalMemory, memory["memory_id"]).status == "deleted"


def test_exact_reminder_and_ambiguous_matter_follow_existing_delivery_rules(database):
    cfg, sessions = database
    due = datetime.now(timezone.utc) + timedelta(days=1)
    provider = DecisionProvider(
        decision(
            reply="明天上午十点提醒你带钥匙。",
            intent_labels=["set_reminder"],
            reminder_commands=[
                {
                    "content": "带钥匙",
                    "next_step": None,
                    "time_precision": "instant",
                    "scheduled_at": due.isoformat(),
                    "timezone_name": "Asia/Shanghai",
                    "mention_policy": "on_due",
                }
            ],
        ),
        decision(
            reply="我先把下个月续费这件事记下来，时间确定后再设提醒。",
            intent_labels=["set_reminder"],
            reminder_commands=[
                {
                    "content": "下个月续费",
                    "next_step": "确认具体日期",
                    "time_precision": "month",
                    "scheduled_at": None,
                    "timezone_name": "Asia/Shanghai",
                    "mention_policy": "when_relevant",
                }
            ],
        ),
    )
    with TestClient(create_app(cfg, provider)) as client:
        _, conversation_id = setup(client)
        assert send(client, conversation_id, "exact", "明天十点提醒我带钥匙").status_code == 200
        assert send(client, conversation_id, "month", "下个月提醒我续费").status_code == 200
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(OngoingMatter)) == 2
        assert session.scalar(select(func.count()).select_from(Reminder)) == 1


def test_state_and_relationship_apply_only_after_completed_turns_and_distinct_evidence(database):
    cfg, sessions = database
    snapshot = {"familiarity": "逐渐熟悉", "trust": "愿意认真倾听", "closeness": "仍有边界"}
    provider = DecisionProvider(
        decision(
            reply="我听见了。",
            intent_labels=["state_change", "relationship_signal"],
            state={
                "description": "因用户认真倾听而稍感安心",
                "persistence": "transient",
                "expression_effect": "语气稍放松",
            },
            relationship={
                "evidence": [
                    {
                        "aspect": "trust",
                        "direction": "strengthen",
                        "reason": "用户明确表示愿意认真倾听",
                        "evidence_kind": "observed_interaction",
                    }
                ],
                "snapshot": snapshot,
                "reason": "出现第一条信任依据",
            },
        ),
        decision(
            reply="谢谢你再次尊重我的决定。",
            intent_labels=["relationship_signal"],
            relationship={
                "evidence": [
                    {
                        "aspect": "familiarity",
                        "direction": "strengthen",
                        "reason": "用户再次尊重角色的自主决定",
                        "evidence_kind": "observed_interaction",
                    }
                ],
                "snapshot": snapshot,
                "reason": "两个独立轮次形成稳定依据",
            },
        ),
    )
    with TestClient(create_app(cfg, provider)) as client:
        instance_id, conversation_id = setup(client)
        first = send(client, conversation_id, "one", "我会认真听你的想法")
        assert any(item["effect"] == "state" for item in first.json()["effects"])
        with sessions() as session:
            assert session.get(CharacterState, instance_id).description
            assert session.get(Relationship, instance_id) is None
        send(client, conversation_id, "two", "这次也由你自己决定")
    with sessions() as session:
        assert session.get(Relationship, instance_id).trust == "愿意认真倾听"
        assert session.scalar(select(func.count()).select_from(RelationshipEvidence)) == 2
        assert session.scalar(select(func.count()).select_from(RelationshipRevision)) == 1


def test_effect_failure_preserves_reply_and_outbox_can_recover(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    provider = DecisionProvider(
        decision(
            reply="我会处理这条请求。",
            intent_labels=["set_reminder"],
            reminder_commands=[
                {
                    "content": "带钥匙",
                    "next_step": None,
                    "time_precision": "instant",
                    "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                    "timezone_name": "Mars/Olympus",
                    "mention_policy": "on_due",
                }
            ],
        )
    )
    effects = ConversationEffectService(sessions)
    response = ConversationService(
        repo, ConversationDecisionProvider(provider), effects
    ).send("alice", conversation_id, "bad-target", "明天提醒我带钥匙")
    assert response.text == ConversationService.UNCONFIRMED_OPERATION_REPLY
    assert response.effects[0]["status"] == "failed"
    assert response.effects[0]["error_code"] == "invalid_reminder_timezone"
    with sessions() as session:
        assert session.get(Message, response.message_id).text == response.text

    recovery_provider = DecisionProvider(
        decision(
            reply="我记住了。",
            intent_labels=["remember"],
            memory_commands=[
                {
                    "action": "remember",
                    "content": "用户喜欢清晨散步",
                    "memory_id": None,
                    "expected_revision": None,
                }
            ],
        )
    )
    pending = ConversationService(
        repo, ConversationDecisionProvider(recovery_provider)
    ).send("alice", conversation_id, "recover", "请记住我喜欢清晨散步")
    assert pending.text == ConversationService.UNCONFIRMED_OPERATION_REPLY
    with sessions() as session:
        assert session.scalar(
            select(PersonalMemory).where(PersonalMemory.content == "用户喜欢清晨散步")
        ) is None
    recovered = effects.run_turn(pending.turn_id)
    assert recovered[0]["status"] == "committed"
    duplicate = ConversationService(
        repo, ConversationDecisionProvider(recovery_provider), effects
    ).send("alice", conversation_id, "recover", "请记住我喜欢清晨散步")
    assert duplicate.text == "我记住了。"
    with sessions() as session:
        assert session.scalar(
            select(PersonalMemory).where(PersonalMemory.content == "用户喜欢清晨散步")
        )
