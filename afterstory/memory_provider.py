import json

from afterstory.domain import ChatMessage, ProviderError
from afterstory.memory_contracts import MemoryExtractionResult, SummaryCandidate


class StructuredMemoryProvider:
    """Strict JSON adapter over the configured text provider."""

    def __init__(self, text_provider):
        self.text_provider = text_provider

    def _generate_json(self, instruction, payload, *, max_tokens):
        messages = [
            ChatMessage("system", instruction),
            ChatMessage(
                "user",
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            ),
        ]
        generate_json = getattr(self.text_provider, "generate_json", None)
        response = (
            generate_json(messages, max_tokens=max_tokens)
            if generate_json
            else self.text_provider.generate(messages)
        )
        try:
            json.loads(response)
        except (json.JSONDecodeError, TypeError):
            raise ProviderError("memory_provider_invalid_json") from None
        return response

    def extract(self, messages, existing_memories=None):
        schema = json.dumps(
            MemoryExtractionResult.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        value = self._generate_json(
            "你是 AfterStory 的记忆整理器。只输出一个 JSON 对象，不输出 Markdown。"
            "根对象必须包含 schema_version=1.0 和 operations 数组，并严格符合给出的 JSON Schema；"
            "不得增加字段，不得省略必填字段。没有值得保存的内容时 operations 输出空数组。"
            "只提取用户明确表达且未来有价值的稳定事实、偏好或经历；"
            "假设、角色扮演、提问中的前提和临时情绪不要保存。"
            "source ID 只能逐字复制输入消息中的 ID，quote 必须来自对应消息。"
            "existing_memories 是同一角色实例的当前有效候选。"
            "明确纠正已有内容时必须使用 action=correct，并逐字复制对应 memory_id；"
            "同一事件出现后续进展时使用 action=supplement，保留原事件的 occurred_at，"
            "把新进展及其日期写进 summary、outcome 或 open_question；"
            "重复表达使用 no_change，含糊冲突使用 defer。"
            "不要把助手说的话当成用户事实。"
            "时间应以来源消息的 recorded_at、timezone_name 和 timezone_source 为基准解释；"
            "仍不能可靠确定时，precision 使用 unknown 且 start/end 为 null。"
            "JSON Schema：" + schema,
            {
                "schema_version": "1.0",
                "messages": messages,
                "existing_memories": existing_memories or [],
            },
            max_tokens=2048,
        )
        return MemoryExtractionResult.model_validate_json(value).operations

    def summarize(self, messages):
        schema = json.dumps(
            SummaryCandidate.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        value = self._generate_json(
            "你是 AfterStory 的分段摘要器。只输出一个 JSON 对象，不输出 Markdown。"
            "按话题记录发展、结论和未完问题；covered_turn_ids 必须按输入轮次顺序完整覆盖，"
            "source_message_ids 只能逐字复制输入。不得增加字段或省略必填字段。"
            "输出必须严格符合以下 JSON Schema：" + schema,
            {"schema_version": "1.0", "messages": messages},
            max_tokens=4096,
        )
        return SummaryCandidate.model_validate_json(value)
