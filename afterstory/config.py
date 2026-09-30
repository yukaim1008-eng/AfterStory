from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class ModelProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    provider: Literal["deepseek", "openai_compatible", "fake"]
    base_url: str
    api_key: SecretStr = SecretStr("")
    model: str
    timeout_seconds: float = Field(default=60, gt=0, le=300)
    max_tokens: int = Field(default=1024, ge=1, le=8192)


def default_models():
    return {
        "deepseek": dict(
            provider="deepseek", base_url="https://api.deepseek.com", model="deepseek-v4-flash"
        ),
        "fake": dict(provider="fake", base_url="", model="engineering-test"),
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )
    app_name: str = "AfterStory"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://afterstory:afterstory_local@127.0.0.1:54329/afterstory"
    )
    dev_user_id: str = "local-user"
    llm_active_model: str = "deepseek"
    llm_models: dict[str, ModelProfile] = Field(default_factory=default_models)

    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        def model_source(source):
            def read():
                data = source()
                profiles = {}
                suffixes = (
                    "provider",
                    "base_url",
                    "api_key",
                    "model",
                    "timeout_seconds",
                    "max_tokens",
                )
                for key, value in source.env_vars.items():
                    for suffix in suffixes:
                        if key.endswith("_" + suffix):
                            name = key[: -(len(suffix) + 1)]
                            if name in {"llm", "llm_active", "tts", "asr", "embedding"}:
                                break
                            if name and "__" not in name and value is not None:
                                profiles.setdefault(name, {})[suffix] = value
                            break
                if profiles:
                    data["llm_models"] = profiles
                return data

            return read

        return (
            init_settings,
            model_source(env_settings),
            model_source(dotenv_settings),
            file_secret_settings,
        )

    @field_validator("llm_models", mode="before")
    @classmethod
    def merge_profiles(cls, value):
        defaults = default_models()
        for name, profile in value.items():
            defaults[name] = (
                {**defaults.get(name, {}), **profile} if isinstance(profile, dict) else profile
            )
        return defaults

    @property
    def active_model(self) -> ModelProfile:
        return self.llm_models[self.llm_active_model]

    turn_lease_seconds: int = Field(default=120, ge=1)
    history_turns: int = Field(default=12, ge=1, le=50)
    memory_context_items: int = Field(default=20, ge=0, le=100)
    memory_context_tokens: int = Field(default=3000, ge=0, le=20000)
    chat_input_tokens: int = Field(default=24000, ge=4000, le=200000)
    chat_context_overhead_tokens: int = Field(default=1800, ge=0, le=10000)
    character_context_tokens: int = Field(default=2500, ge=1, le=20000)
    dynamics_context_tokens: int = Field(default=500, ge=0, le=5000)
    continuity_context_tokens: int = Field(default=4000, ge=0, le=30000)
    history_context_tokens: int = Field(default=8200, ge=0, le=50000)
    current_message_tokens: int = Field(default=4000, ge=1, le=20000)
    memory_extraction_input_tokens: int = Field(default=12000, ge=2000, le=100000)
    memory_extraction_candidate_items: int = Field(default=20, ge=0, le=100)
    memory_extraction_candidate_tokens: int = Field(default=8000, ge=0, le=50000)
    summary_input_tokens: int = Field(default=24000, ge=4000, le=100000)
    summary_source_tokens: int = Field(default=22000, ge=2000, le=100000)
    summary_segment_turns: int = Field(default=20, ge=2, le=100)
    # Kept only for older callers that construct ContextAssembler directly.
    memory_context_chars: int = Field(default=6000, ge=0, le=50000)
    user_timezone: str = "Asia/Shanghai"
    memory_worker_poll_seconds: float = Field(default=2.0, ge=0.2, le=60)

    @model_validator(mode="after")
    def validate_runtime(self):
        if not self.database_url.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        if self.llm_active_model not in self.llm_models:
            raise ValueError("LLM_ACTIVE_MODEL must reference a configured model profile")
        if self.turn_lease_seconds <= self.active_model.timeout_seconds + 10:
            raise ValueError("TURN_LEASE_SECONDS must exceed the active model timeout by >10s")
        planned = (
            self.character_context_tokens
            + self.memory_context_tokens
            + self.dynamics_context_tokens
            + self.continuity_context_tokens
            + self.history_context_tokens
            + self.current_message_tokens
            + self.chat_context_overhead_tokens
        )
        if planned > self.chat_input_tokens:
            raise ValueError("CHAT_INPUT_TOKENS must cover all configured context budgets")
        if self.summary_source_tokens >= self.summary_input_tokens:
            raise ValueError("SUMMARY_SOURCE_TOKENS must leave room for summary instructions")
        if self.memory_extraction_candidate_tokens >= self.memory_extraction_input_tokens:
            raise ValueError(
                "MEMORY_EXTRACTION_CANDIDATE_TOKENS must leave room for current messages"
            )
        try:
            ZoneInfo(self.user_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("USER_TIMEZONE must be an IANA timezone") from exc
        return self
