import json

import httpx
import pytest

from afterstory.config import Settings
from afterstory.domain import ChatMessage, ProviderError
from afterstory.providers import ChatCompletionsProvider


def config():
    return Settings(_env_file=None, llm_api_key="test-only-not-real")


def test_deepseek_request_and_no_reasoning_in_reply():
    def handle(request):
        body = json.loads(request.content)
        assert body["model"] == "deepseek-v4-flash"
        assert body["thinking"] == {"type": "disabled"}
        assert body["stream"] is False
        assert request.url.path == "/chat/completions"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "你好", "reasoning_content": "not to be returned"},
                    }
                ]
            },
        )

    provider = ChatCompletionsProvider(config(), httpx.MockTransport(handle))
    assert provider.generate([ChatMessage("user", "hi")]) == "你好"


@pytest.mark.parametrize(
    "response,code",
    [
        (httpx.Response(401, text="private upstream details"), "llm_http_error"),
        (httpx.Response(200, json={}), "llm_invalid_response"),
        (
            httpx.Response(
                200,
                json={"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]},
            ),
            "llm_incomplete_response",
        ),
        (
            httpx.Response(
                200, json={"choices": [{"finish_reason": "stop", "message": {"content": " "}}]}
            ),
            "llm_empty_response",
        ),
    ],
)
def test_provider_errors_sanitized(response, code):
    provider = ChatCompletionsProvider(config(), httpx.MockTransport(lambda r: response))
    with pytest.raises(ProviderError) as exc:
        provider.generate([ChatMessage("user", "hello")])
    assert str(exc.value) == code


def test_timeout_and_missing_key():
    def timeout(request):
        raise httpx.ReadTimeout("private information")

    provider = ChatCompletionsProvider(config(), httpx.MockTransport(timeout))
    with pytest.raises(ProviderError, match="llm_timeout"):
        provider.generate([ChatMessage("user", "hi")])
    with pytest.raises(ProviderError, match="llm_key_missing"):
        ChatCompletionsProvider(Settings(_env_file=None)).generate([])
