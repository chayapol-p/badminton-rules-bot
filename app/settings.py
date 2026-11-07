"""
Settings for the RAG workshop.

Reads the API keys and model names from the .env file at the project root.
Environment variables override the .env file.

If a key is missing or empty, the app stops at startup with a message that
names the missing key and says where to put it. That is better than failing
later, deep inside an API call, with an unclear authentication error.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root: the folder that holds .env and pyproject.toml
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Error raised when a required setting is missing, with a message a person can act on
class MissingSettingError(RuntimeError):
    pass


# All settings in one place. Field names match the .env names, in lower case.
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API keys: required. SecretStr keeps them out of logs, errors and printed output.
    mistral_api_key: SecretStr
    anthropic_api_key: SecretStr

    # Model names, checked against docs.mistral.ai on 1 Nov 2026.
    # Pinned to fixed major.minor IDs: aliases such as mistral-large-latest can change silently.
    # Large 4 is in Public Preview, so it can still change; re-check its card before each eval run.
    mistral_answer_model: str = "mistral-large-4-0"
    mistral_draft_model: str = "mistral-small-2603"
    mistral_embedding_model: str = "mistral-embed-2312"
    # Large 4 always thinks; this pins how much (low, medium or high), so every eval run uses the same setting
    mistral_reasoning_effort: str = "low"
    claude_comparison_model: str = "claude-haiku-5-5"
    # The answer judge (Stage 2): another model family than the answer model, to avoid self-preference bias
    claude_judge_model: str = "claude-sonnet-5-5"

    # Database address: Supabase > Connect > Session pooler. Optional, because only vector search needs it.
    database_url: SecretStr | None = None

    # A key line left as "MISTRAL_API_KEY=" in .env arrives as an empty string: treat it as missing
    @field_validator("mistral_api_key", "anthropic_api_key")
    @classmethod
    def reject_empty_key(cls, key: SecretStr) -> SecretStr:
        if not key.get_secret_value().strip():
            raise ValueError("the key is empty")
        return key


# Load the settings once and reuse them. Turns pydantic's error into a plain message.
@lru_cache
def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as error:
        problem_names = sorted({str(problem["loc"][0]).upper() for problem in error.errors()})
        raise MissingSettingError(
            f"Missing or empty setting: {', '.join(problem_names)}. "
            f"Copy .env.example to .env in {PROJECT_ROOT} and paste the key after the = sign."
        ) from None


# Return the database address, or stop with a message that says where to find it
def require_database_url(settings: Settings) -> str:
    if settings.database_url is None or not settings.database_url.get_secret_value().strip():
        raise MissingSettingError(
            "Missing setting: DATABASE_URL. In Supabase, open your project > Connect > Session pooler, "
            "copy the URI, put your database password in it, and paste it into .env."
        )
    return settings.database_url.get_secret_value()
