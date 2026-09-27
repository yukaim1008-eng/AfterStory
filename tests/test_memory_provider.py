import json

import pytest
from pydantic import ValidationError

from afterstory.domain import ProviderError
from afterstory.memory_provider import StructuredMemoryProvider


class JsonTextProvider:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.max_tokens = []

    def generate_json(self, messages, max_tokens=None):
        self.calls.append(messages)
        self.max_tokens.append(max_tokens)
        return json.dumps(self.payload, ensure_ascii=False)


def source_message():
    return {
        "message_id": "message-1",
        "turn_id": "turn-1",
        "conversation_id": "conversation-1",
        "role": "user",
        "text": "我喝咖啡不加糖。",
    }


def test_structured_memory_provider_supplies_contract_and_parses_envelope():
    provider = JsonTextProvider(
        {
            "schema_version": "1.0",
            "operations": [
                {
                    "action": "create",
                    "target_memory_id": None,
                    "reason": "稳定偏好",
                    "memory": {
                        "schema_version": "1.0",
                        "evidence": "user_explicit",
                        "importance_reason": "未来饮食交流有用",
                        "payload": {
                            "kind": "preference",
                            "subject": "用户",
                            "attribute": "咖啡甜度",
                            "value": "不加糖",
                            "conditions": "",
                            "scope": "reality",
                            "valid_time": {
                                "precision": "unknown",
                                "start": None,
                                "end": None,
                                "original_text": "",
                                "timezone": "",
                                "timezone_source": "unknown",
                            },
                        },
                        "sources": [
                            {
                                "message_id": "message-1",
                                "turn_id": "turn-1",
                                "conversation_id": "conversation-1",
                                "role": "user",
                                "quote": "我喝咖啡不加糖。",
                            }
                        ],
                    },
                }
            ],
        }
    )

    result = StructuredMemoryProvider(provider).extract(
        [source_message()],
        [
            {
                "memory_id": "memory-1",
                "revision": 1,
                "memory_type": "preference",
                "content": "用户的咖啡甜度：不加糖",
            }
        ],
    )

    assert result[0].memory.payload.value == "不加糖"
    assert "JSON Schema" in provider.calls[0][0].content
    assert "memory-1" in provider.calls[0][1].content


def test_structured_memory_provider_rejects_unknown_output_fields():
    provider = JsonTextProvider(
        {"schema_version": "1.0", "operations": [], "unexpected": True}
    )
    with pytest.raises(ValidationError):
        StructuredMemoryProvider(provider).extract([source_message()])


def test_extraction_caps_candidate_count_and_token_budget():
    provider = JsonTextProvider({"schema_version": "1.0", "operations": []})
    memories = [
        {"memory_id": f"memory-{index}", "content": "候选"}
        for index in range(30)
    ]
    adapter = StructuredMemoryProvider(provider, extraction_candidate_items=20)
    adapter.extract([source_message()], memories)
    payload = json.loads(provider.calls[0][1].content)
    assert len(payload["existing_memories"]) == 20
    assert provider.max_tokens == [2048]

    provider = JsonTextProvider({"schema_version": "1.0", "operations": []})
    adapter = StructuredMemoryProvider(provider, extraction_candidate_tokens=1)
    adapter.extract([source_message()], memories)
    assert json.loads(provider.calls[0][1].content)["existing_memories"] == []


def test_structured_provider_rejects_oversized_inputs_before_api_call():
    provider = JsonTextProvider({"schema_version": "1.0", "operations": []})
    with pytest.raises(ProviderError, match="memory_provider_input_too_large"):
        StructuredMemoryProvider(provider, extraction_input_tokens=10).extract(
            [source_message()]
        )
    assert provider.calls == []

    with pytest.raises(ProviderError, match="summary_provider_input_too_large"):
        StructuredMemoryProvider(provider, summary_input_tokens=10).summarize(
            [source_message()]
        )
    assert provider.calls == []
