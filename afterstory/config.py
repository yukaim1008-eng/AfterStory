from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )
    app_name: str = "AfterStory"
    database_url: SecretStr = SecretStr(
        "postgresql+psycopg://afterstory:afterstory_local@127.0.0.1:54329/afterstory"
    )
    dev_user_id: str = "local-user"
    llm_provider: Literal["deepseek", "openai_compatible", "fake"] = "deepseek"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "deepseek-v4-flash"
    llm_timeout_seconds: float = Field(default=60, gt=0, le=300)
    llm_max_tokens: int = Field(default=1024, ge=1, le=8192)
    turn_lease_seconds: int = Field(default=120, ge=1)
    history_turns: int = Field(default=12, ge=1, le=50)

    @model_validator(mode="after")
    def validate_runtime(self):
        if not self.database_url.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        if self.turn_lease_seconds <= self.llm_timeout_seconds + 10:
            raise ValueError("TURN_LEASE_SECONDS must exceed LLM_TIMEOUT_SECONDS by >10s")
        return self
