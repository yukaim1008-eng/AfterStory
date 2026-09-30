import json

import httpx
import pytest
from pydantic import ValidationError

from afterstory.api import create_app
from afterstory.config import Settings
from afterstory.domain import ChatMessage
from afterstory.providers import ChatCompletionsProvider


def test_profiles_load_from_env_and_switch_as_a_unit(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "LLM_ACTIVE_MODEL=second\n"
        "DEEPSEEK_API_KEY=first-secret\n"
        "SECOND_PROVIDER=openai_compatible\n"
        "SECOND_BASE_URL=https://second.example/v1\n"
        "SECOND_MODEL=second-model\n"
        "SECOND_API_KEY=second-secret\n",
        encoding="utf-8",
    )
    calls = []

    def handle(request):
        calls.append(
            (str(request.url), request.headers["Authorization"], json.loads(request.content))
        )
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": "ok"}}]}
        )

    for active in ("deepseek", "second"):
        cfg = Settings(_env_file=env, llm_active_model=active)
        assert len(cfg.llm_models) == 3
        assert "second-secret" not in repr(cfg)
        ChatCompletionsProvider(cfg, httpx.MockTransport(handle)).generate(
            [ChatMessage("user", "hello")]
        )
    assert calls[0][0] == "https://api.deepseek.com/chat/completions"
    assert calls[0][1] == "Bearer first-secret"
    assert calls[0][2]["model"] == "deepseek-v4-flash"
    assert calls[1][0] == "https://second.example/v1/chat/completions"
    assert calls[1][1] == "Bearer second-secret"
    assert calls[1][2]["model"] == "second-model"
    assert "thinking" not in calls[1][2]


def test_unknown_profile_and_active_timeout_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_active_model="missing")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_models={"deepseek": {"timeout_seconds": 115}})


def test_profile_environment_override(monkeypatch):
    monkeypatch.setenv("LLM_ACTIVE_MODEL", "fake")
    cfg = Settings(_env_file=None)
    assert cfg.active_model.provider == "fake"
    assert "deepseek" in cfg.llm_models


def test_default_token_budgets_are_consistent():
    cfg = Settings(_env_file=None)
    assert cfg.chat_input_tokens == 24000
    assert cfg.active_model.max_tokens == 1024
    assert cfg.memory_context_tokens == 3000
    assert cfg.chat_context_overhead_tokens == 1800
    assert cfg.history_context_tokens == 8200
    assert cfg.memory_extraction_input_tokens == 12000
    assert cfg.memory_extraction_candidate_items == 20
    assert cfg.memory_extraction_candidate_tokens == 8000
    assert cfg.summary_input_tokens == 24000
    assert cfg.summary_source_tokens == 22000
    assert cfg.summary_segment_turns == 20


@pytest.mark.parametrize(
    "override",
    [
        {"chat_input_tokens": 23000},
        {"summary_source_tokens": 24000},
        {"memory_extraction_candidate_tokens": 12000},
    ],
)
def test_inconsistent_token_budgets_are_rejected(override):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **override)


def test_application_wires_runtime_token_budgets_into_context_and_retrieval():
    cfg = Settings(_env_file=None, llm_active_model="fake")
    app = create_app(cfg)
    repository = app.state.repository
    assert repository.context.total_tokens == cfg.chat_input_tokens
    assert repository.context.memory_tokens == cfg.memory_context_tokens
    assert repository.context.history_tokens == cfg.history_context_tokens
    assert repository.context.current_message_tokens == cfg.current_message_tokens
    assert repository.retrieval.max_items == cfg.memory_context_items
    assert repository.retrieval.max_tokens == cfg.memory_context_tokens
