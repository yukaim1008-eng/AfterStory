import httpx

from afterstory.config import Settings
from afterstory.domain import ChatMessage, ProviderError


class FakeProvider:
    def generate(self, messages: list[ChatMessage]) -> str:
        count = sum(m.role == "user" for m in messages)
        return f"[工程测试回复；上下文含 {count} 条用户消息] {messages[-1].content}"


class ChatCompletionsProvider:
    def __init__(self, settings: Settings, transport=None):
        self.settings = settings
        self.transport = transport

    def generate(self, messages: list[ChatMessage]) -> str:
        cfg = self.settings.active_model
        key = cfg.api_key.get_secret_value()
        if not key:
            raise ProviderError("llm_key_missing")
        payload = {
            "model": cfg.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "max_tokens": cfg.max_tokens,
        }
        if cfg.provider == "deepseek":
            payload["thinking"] = {"type": "disabled"}
        try:
            with httpx.Client(timeout=cfg.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    cfg.base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json=payload,
                )
                response.raise_for_status()
                choice = response.json()["choices"][0]
                content = choice["message"]["content"]
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
