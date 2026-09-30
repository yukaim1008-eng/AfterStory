from datetime import datetime, timezone

from afterstory.config import Settings
from afterstory.conversation_provider import ConversationDecisionProvider
from afterstory.domain import ChatMessage
from afterstory.memory_contracts import ConservativeTokenCounter
from afterstory.response_policy import RESPONSE_POLICY_VERSION, build_response_policy


def test_response_policy_is_versioned_stable_and_contains_no_runtime_data():
    first = build_response_policy()
    assert RESPONSE_POLICY_VERSION == "1.0"
    assert first == build_response_policy()
    assert "倾诉时先准确回应" in first
    assert "默认最多提出一个" in first
    assert "用户单方面宣布关系升级不能当成已建立事实" in first
    assert "林遥" not in first
    assert "memory-123" not in first


def test_combined_runtime_instructions_fit_reserved_overhead_in_fixed_order():
    now = datetime(2026, 9, 30, tzinfo=timezone.utc)
    policy = build_response_policy()
    orchestrator = ConversationDecisionProvider._instruction(now, "Asia/Shanghai")
    cfg = Settings(_env_file=None)
    assert ConservativeTokenCounter().count(policy + orchestrator) <= (
        cfg.chat_context_overhead_tokens
    )

    normalized = ConversationDecisionProvider._structured_messages(
        [
            ChatMessage("system", "角色定义"),
            ChatMessage("system", "运行时资料"),
            ChatMessage("user", "上一问"),
            ChatMessage("assistant", "上一答"),
            ChatMessage("user", "当前输入"),
        ],
        now,
        "Asia/Shanghai",
    )
    system = normalized[0].content
    assert system.index("角色定义") < system.index("运行时资料")
    assert system.index("运行时资料") < system.index("AfterStory Response Policy 1.0")
    assert system.index("AfterStory Response Policy 1.0") < system.index(
        "AfterStory Conversation Orchestrator 1.0"
    )


def test_plain_provider_receives_policy_without_changing_decision_schema():
    class PlainProvider:
        def __init__(self):
            self.messages = None

        def generate(self, messages):
            self.messages = messages
            return "自然回复"

    provider = PlainProvider()
    result = ConversationDecisionProvider(provider).generate_turn(
        [ChatMessage("system", "角色"), ChatMessage("user", "你好")],
        datetime(2026, 9, 30, tzinfo=timezone.utc),
        "Asia/Shanghai",
    )
    assert result.reply == "自然回复"
    assert result.model_dump() == {
        "schema_version": "1.0",
        "reply": "自然回复",
        "intent_labels": ["chat"],
        "memory_commands": [],
        "reminder_commands": [],
        "state": None,
        "relationship": None,
    }
    assert "AfterStory Response Policy 1.0" in provider.messages[0].content
