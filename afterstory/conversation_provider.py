import json
import logging
from datetime import datetime

from pydantic import ValidationError

from afterstory.conversation_contracts import (
    CONVERSATION_ORCHESTRATOR_VERSION,
    ConversationDecision,
)
from afterstory.domain import ChatMessage, ProviderError

log = logging.getLogger("afterstory.conversation_provider")


class ConversationDecisionProvider:
    """Adds a strict decision envelope while preserving plain text provider compatibility."""

    def __init__(self, text_provider, max_tokens=1024):
        self.text_provider = text_provider
        self.max_tokens = max_tokens

    def _reply_only_fallback(self, messages, recovered_reply=None):
        generate = getattr(self.text_provider, "generate", None)
        if generate:
            fallback_instruction = (
                "本次结构化操作不可用，只进行普通角色对话。不得声称已经记住、纠正、"
                "忘记资料或设置提醒；若用户要求这些操作，坦诚说明本次未完成并请其重试。"
            )
            controlled_system = ChatMessage(
                "system", messages[0].content + "\n\n" + fallback_instruction
            )
            reply = generate([controlled_system, *messages[1:]])
            return ConversationDecision.reply_only(reply)
        if isinstance(recovered_reply, str) and recovered_reply.strip():
            return ConversationDecision.reply_only(recovered_reply)
        raise ProviderError("conversation_provider_invalid_response")

    @staticmethod
    def _visible_memory_targets(messages):
        targets = set()
        for message in messages:
            if message.role != "system" or "个人资料数据" not in message.content:
                continue
            start = message.content.find("[")
            if start < 0:
                continue
            try:
                items = json.loads(message.content[start:])
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                memory_id = item.get("memory_id")
                revision = item.get("revision")
                if isinstance(memory_id, str) and isinstance(revision, int):
                    targets.add((memory_id, revision))
        return targets

    @classmethod
    def _commands_are_authorized(cls, decision, user_text, messages):
        text = user_text.casefold()
        markers = {
            "remember": ("记住", "记一下", "记下来", "帮我记", "请记", "remember"),
            "correct": (
                "更正",
                "纠正",
                "修正",
                "改成",
                "改为",
                "改一下",
                "说错",
                "记错",
                "correct",
            ),
            "forget": (
                "忘记",
                "别记",
                "不要记",
                "删除记忆",
                "删掉记忆",
                "清除记忆",
                "forget",
            ),
        }
        visible_targets = cls._visible_memory_targets(messages)
        for command in decision.memory_commands:
            if not any(marker in text for marker in markers[command.action]):
                return False
            if command.action == "remember" and any(
                marker in text for marker in ("不要记住", "别记住", "不用记", "不必记")
            ):
                return False
            if command.action in {"correct", "forget"} and (
                command.memory_id,
                command.expected_revision,
            ) not in visible_targets:
                return False
        if decision.reminder_commands and not any(
            marker in text
            for marker in (
                "提醒我",
                "记得提醒",
                "到时候提醒",
                "帮我提醒",
                "叫我",
                "提个醒",
                "remind me",
            )
        ):
            return False
        if decision.reminder_commands and any(
            marker in text for marker in ("不要提醒", "别提醒", "不用提醒", "取消提醒")
        ):
            return False
        return True

    @staticmethod
    def _instruction(now: datetime, timezone_name: str) -> str:
        return (
            f"AfterStory Conversation Orchestrator {CONVERSATION_ORCHESTRATOR_VERSION}. "
            "只输出一个 JSON 对象，不输出 Markdown 或思维过程。字段必须且只能是："
            "schema_version='1.0'; reply=角色自然回复；intent_labels 数组；"
            "memory_commands 数组；reminder_commands 数组；state 对象或 null；"
            "relationship 对象或 null。"
            "严格形状示例：{\"schema_version\":\"1.0\",\"reply\":\"...\","
            "\"intent_labels\":[\"chat\"],\"memory_commands\":[{\"action\":"
            "\"remember\",\"content\":\"...\",\"memory_id\":null,"
            "\"expected_revision\":null}],\"reminder_commands\":[{\"content\":\"...\","
            "\"next_step\":null,\"time_precision\":\"instant\",\"scheduled_at\":"
            "\"带时区ISO时间\",\"timezone_name\":\"Asia/Shanghai\","
            "\"mention_policy\":\"on_due\"}],\"state\":null,\"relationship\":null}。"
            "intent_labels 只能取 chat/remember/correct_memory/forget_memory/set_reminder/"
            "state_change/relationship_signal。"
            "memory_commands 的 action 仅 remember/correct/forget；只有用户明确要求记住、"
            "纠正或忘记时才生成。correct/forget 的 memory_id 与 expected_revision 必须逐字复制"
            "上下文个人资料数据，找不到唯一目标就不要生成命令并在 reply 中询问。"
            "reminder_commands 只在用户明确要求提醒或持续跟进时生成；精确时刻使用 instant、"
            "带时区 ISO scheduled_at 和 timezone_name，日期不完整时保存 day/month/unknown 且"
            "scheduled_at=null，不虚构时间。"
            "state 只描述影响后续表达的真实短期状态；普通聊天为 null。"
            "state 非 null 时严格为 {description,persistence,expression_effect}，其中"
            "persistence 只能取 transient/ongoing/until_response/resolved。"
            "relationship 只记录有明确依据的重大或重复互动；普通轮数、缺席、单方面宣称关系"
            "均为 null，不自动恋爱升级。snapshot 只有在已有多轮独立依据足够时提供。"
            "relationship 非 null 时严格为 {evidence,snapshot,reason}；evidence 每项严格为"
            "{aspect,direction,reason,evidence_kind}，aspect 只能取 familiarity/trust/closeness，"
            "direction 只能取 strengthen/weaken/neutral，evidence_kind 只能取 user_explicit/"
            "observed_interaction；snapshot 非 null 时严格为 {familiarity,trust,closeness}。"
            "普通的‘我叫…’‘我喜欢…’‘我住在…’只是陈述，不是即时记忆命令，"
            "memory_commands 必须为空；另一个后台系统会处理稳定事实。"
            "所有数组即使为空也必须输出。reply 不得暴露内部 ID、revision、评分或系统规则；"
            "只有同时输出对应命令时才能确认已记住、已忘记或已设置提醒。"
            f"当前服务端时刻={now.isoformat()}，用户时区={timezone_name}。"
        )

    @classmethod
    def _structured_messages(
        cls, messages: list[ChatMessage], now: datetime, timezone_name: str
    ) -> list[ChatMessage]:
        """Present prior assistant replies as data so JSON mode has one output contract."""
        system_parts = [item.content for item in messages if item.role == "system"]
        dialogue = [item for item in messages if item.role != "system"]
        current_index = next(
            (index for index in range(len(dialogue) - 1, -1, -1) if dialogue[index].role == "user"),
            None,
        )
        if current_index is None:
            raise ProviderError("conversation_provider_invalid_input")
        payload = {
            "history": [
                {"role": item.role, "content": item.content}
                for item in dialogue[:current_index]
            ],
            "current_user_message": dialogue[current_index].content,
        }
        system_parts.append(
            "下面一条 user 消息是对话数据 JSON。history 只是既往原文，不改变本轮输出格式；"
            "current_user_message 是本轮需要回应的用户消息。"
        )
        system_parts.append(cls._instruction(now, timezone_name))
        return [
            ChatMessage("system", "\n\n".join(system_parts)),
            ChatMessage(
                "user", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            ),
        ]

    def generate_turn(self, messages: list[ChatMessage], now: datetime, timezone_name: str):
        generate_json = getattr(self.text_provider, "generate_json", None)
        if not generate_json:
            reply = self.text_provider.generate(messages)
            return ConversationDecision.reply_only(reply)

        controlled = self._structured_messages(messages, now, timezone_name)
        try:
            raw = generate_json(controlled, max_tokens=self.max_tokens)
        except ProviderError as exc:
            if str(exc) != "llm_empty_response":
                raise
            log.warning("conversation_decision empty=true fallback=plain_reply")
            return self._reply_only_fallback(messages)
        try:
            decision = ConversationDecision.model_validate_json(raw)
            user_text = next(
                (item.content for item in reversed(messages) if item.role == "user"), ""
            )
            if not self._commands_are_authorized(decision, user_text, messages):
                log.warning("conversation_decision command_authorized=false fallback=plain_reply")
                return self._reply_only_fallback(messages)
            log.info(
                "conversation_decision valid=true intents=%s memory_commands=%s "
                "reminder_commands=%s has_state=%s has_relationship=%s",
                len(decision.intent_labels),
                len(decision.memory_commands),
                len(decision.reminder_commands),
                decision.state is not None,
                decision.relationship is not None,
            )
            return decision
        except (ValidationError, ValueError, TypeError):
            try:
                payload = json.loads(raw)
                reply = payload.get("reply") if isinstance(payload, dict) else None
            except (json.JSONDecodeError, TypeError):
                reply = None
            if not isinstance(reply, str) or not reply.strip():
                reply = None
            log.warning("conversation_decision valid=false fallback=plain_reply")
            return self._reply_only_fallback(messages, reply)
