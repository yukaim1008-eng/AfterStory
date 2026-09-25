import json

from afterstory.domain import ChatMessage, ProviderError
from afterstory.memory_contracts import MemoryOperationCandidate, SummaryCandidate


class StructuredMemoryProvider:
    """Strict JSON adapter over the configured text provider."""

    def __init__(self, text_provider):
        self.text_provider = text_provider

    def _generate_json(self, instruction, payload):
        response = self.text_provider.generate(
            [
                ChatMessage("system", instruction),
                ChatMessage(
                    "user",
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                ),
            ]
        )
        try:
            return json.loads(response)
        except (json.JSONDecodeError, TypeError):
            raise ProviderError("memory_provider_invalid_json") from None

    def extract(self, messages):
        value = self._generate_json(
            "你是 AfterStory 的记忆整理器。只输出 JSON 数组，不输出 Markdown。"
            "只提取用户明确表达且未来有价值的事实、偏好或经历；假设、角色扮演和临时情绪应 defer。"
            "每项必须符合 MemoryOperationCandidate 1.0，并且 source ID 只能取输入。",
            {"schema_version": "1.0", "messages": messages},
        )
        if not isinstance(value, list):
            raise ProviderError("memory_provider_invalid_shape")
        return [MemoryOperationCandidate.model_validate(item) for item in value]

    def summarize(self, messages):
        value = self._generate_json(
            "你是 AfterStory 的分段摘要器。只输出一个 JSON 对象，不输出 Markdown。"
            "按话题记录发展、结论和未完问题；covered_turn_ids 必须按输入轮次顺序完整覆盖，"
            "source_message_ids 只能取输入。输出必须符合 SummaryCandidate 1.0。",
            {"schema_version": "1.0", "messages": messages},
        )
        return SummaryCandidate.model_validate(value)
