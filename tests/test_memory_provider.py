import json

import pytest
from pydantic import ValidationError

from afterstory.memory_provider import StructuredMemoryProvider


class JsonTextProvider:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate_json(self, messages, max_tokens=None):
        self.calls.append(messages)
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
