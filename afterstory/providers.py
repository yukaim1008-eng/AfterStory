import logging

import httpx

from afterstory.config import Settings
from afterstory.domain import ChatMessage, ProviderError

provider_log = logging.getLogger("afterstory.provider")


def _usage_value(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class FakeProvider:
    def generate(self, messages: list[ChatMessage]) -> str:
        count = sum(m.role == "user" for m in messages)
        return f"[工程测试回复；上下文含 {count} 条用户消息] {messages[-1].content}"


class ChatCompletionsProvider:
    def __init__(self, settings: Settings, transport=None):
        self.settings = settings
        self.transport = transport

    def generate(self, messages: list[ChatMessage]) -> str:
        return self._generate(messages, json_mode=False)

    def generate_json(self, messages: list[ChatMessage], max_tokens: int | None = None) -> str:
        """Request a JSON object from providers that support OpenAI JSON mode."""
        return self._generate(messages, json_mode=True, max_tokens=max_tokens)

    def _generate(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool,
        max_tokens: int | None = None,
    ) -> str:
        cfg = self.settings.active_model
        key = cfg.api_key.get_secret_value()
        if not key:
            raise ProviderError("llm_key_missing")
        payload = {
            "model": cfg.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "max_tokens": max_tokens or cfg.max_tokens,
        }
        if cfg.provider == "deepseek":
            payload["thinking"] = {"type": "disabled"}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            with httpx.Client(timeout=cfg.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    cfg.base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                choice = data["choices"][0]
                content = choice["message"]["content"]
                usage = data.get("usage") or {}
                provider_log.info(
                    "llm_usage profile=%s json_mode=%s prompt_tokens=%s "
                    "completion_tokens=%s total_tokens=%s",
                    self.settings.llm_active_model,
                    json_mode,
                    _usage_value(usage.get("prompt_tokens")),
                    _usage_value(usage.get("completion_tokens")),
                    _usage_value(usage.get("total_tokens")),
                )
                if choice.get("finish_reason") != "stop":
                    raise ProviderError("llm_incomplete_response")
                if not isinstance(content, str) or not content.strip():
                    raise ProviderError("llm_empty_response")
                return content.strip()
        except httpx.TimeoutException:
            raise ProviderError("llm_timeout") from None
        except httpx.HTTPStatusError:
            raise ProviderError("llm_http_error") from None
        except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("llm_invalid_response") from None
