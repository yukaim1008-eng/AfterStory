import json

from afterstory.domain import ChatMessage, ProviderError
from afterstory.memory_contracts import (
    ConservativeTokenCounter,
    MemoryExtractionResult,
    SummaryCandidate,
)

MEMORY_EXTRACTION_OUTPUT_TOKENS = 2048
SUMMARY_OUTPUT_TOKENS = 4096


class StructuredMemoryProvider:
    """Strict JSON adapter over the configured text provider."""

    def __init__(
        self,
        text_provider,
        *,
        extraction_input_tokens=12000,
        extraction_candidate_items=20,
        extraction_candidate_tokens=8000,
        summary_input_tokens=24000,
        token_counter=None,
    ):
        self.text_provider = text_provider
        self.extraction_input_tokens = extraction_input_tokens
        self.extraction_candidate_items = extraction_candidate_items
        self.extraction_candidate_tokens = extraction_candidate_tokens
        self.summary_input_tokens = summary_input_tokens
        self.token_counter = token_counter or ConservativeTokenCounter()

    @staticmethod
    def _json(payload):
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _input_tokens(self, instruction, payload):
        # Add message framing overhead to the same conservative estimate used by runtime context.
        return self.token_counter.count(instruction) + self.token_counter.count(
            self._json(payload)
        ) + 8

    def _generate_json(self, instruction, payload, *, max_tokens):
        messages = [
            ChatMessage("system", instruction),
            ChatMessage(
                "user",
                self._json(payload),
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
        instruction = (
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
            "JSON Schema：" + schema
        )
        selected = []
        for item in (existing_memories or [])[: self.extraction_candidate_items]:
            candidate = selected + [item]
            if self.token_counter.count(self._json(candidate)) > self.extraction_candidate_tokens:
                break
            selected = candidate
        payload = {
            "schema_version": "1.0",
            "messages": messages,
            "existing_memories": selected,
        }
        while selected and self._input_tokens(instruction, payload) > self.extraction_input_tokens:
            selected.pop()
            payload["existing_memories"] = selected
        if self._input_tokens(instruction, payload) > self.extraction_input_tokens:
            raise ProviderError("memory_provider_input_too_large")
        value = self._generate_json(
            instruction,
            payload,
            max_tokens=MEMORY_EXTRACTION_OUTPUT_TOKENS,
        )
        return MemoryExtractionResult.model_validate_json(value).operations

    def summarize(self, messages):
        schema = json.dumps(
            SummaryCandidate.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        instruction = (
            "你是 AfterStory 的分段摘要器。只输出一个 JSON 对象，不输出 Markdown。"
            "按话题记录发展、结论和未完问题；covered_turn_ids 必须按输入轮次顺序完整覆盖，"
            "source_message_ids 只能逐字复制输入。不得增加字段或省略必填字段。"
            "输出必须严格符合以下 JSON Schema：" + schema
        )
        payload = {"schema_version": "1.0", "messages": messages}
        if self._input_tokens(instruction, payload) > self.summary_input_tokens:
            raise ProviderError("summary_provider_input_too_large")
        value = self._generate_json(
            instruction,
            payload,
            max_tokens=SUMMARY_OUTPUT_TOKENS,
        )
        return SummaryCandidate.model_validate_json(value)
