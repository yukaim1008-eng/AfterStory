import json

import httpx
import pytest

from afterstory.config import Settings
from afterstory.domain import ChatMessage, ProviderError
from afterstory.providers import ChatCompletionsProvider


def config():
    return Settings(_env_file=None, llm_models={"deepseek": {"api_key": "test-only-not-real"}})


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


def test_provider_logs_only_usage_metadata(caplog):
    def handle(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": "回复"}}],
                "usage": {
                    "prompt_tokens": 321,
                    "completion_tokens": 45,
                    "total_tokens": 366,
                },
            },
        )

    caplog.set_level("INFO", logger="afterstory.provider")
    provider = ChatCompletionsProvider(config(), httpx.MockTransport(handle))
    provider.generate([ChatMessage("user", "private-user-content")])
    record = caplog.records[-1].getMessage()
    assert "prompt_tokens=321" in record
    assert "completion_tokens=45" in record
    assert "total_tokens=366" in record
    assert "private-user-content" not in record
    assert "test-only-not-real" not in record


def test_deepseek_json_mode_is_explicit():
    def handle(request):
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert body["max_tokens"] == 2048
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": '{"ok":true}'}}
                ]
            },
        )

    provider = ChatCompletionsProvider(config(), httpx.MockTransport(handle))
    assert (
        provider.generate_json([ChatMessage("system", "output json")], max_tokens=2048)
        == '{"ok":true}'
    )


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
