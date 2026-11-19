"""
Settings for the bot, the app, the evals and the scripts. It sits at the project root, so the bot reads its
settings without importing the web app.

Reads the API keys and model names from the .env file at the project root.
Environment variables override the .env file.

If the Mistral key is missing or empty, the app stops at startup with a message
that names the key and says where to put it. That is better than failing later,
deep inside an API call, with an unclear authentication error. The Anthropic key
is optional: only the answer judge and the experiment runs need it, and they ask
for it through require_anthropic_api_key().
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root: the folder that holds .env and pyproject.toml
PROJECT_ROOT = Path(__file__).resolve().parent


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

    # API keys. SecretStr keeps them out of logs, errors and printed output.
    # The Mistral key is required; the Anthropic key only for the answer judge and the experiment runs.
    mistral_api_key: SecretStr
    anthropic_api_key: SecretStr | None = None

    # Model names, checked against docs.mistral.ai on 1 Nov 2026.
    # Pinned to fixed major.minor IDs: aliases such as mistral-large-latest can change silently.
    # Large 4 is in Public Preview, so it can still change; re-check its card before each eval run.
    mistral_answer_model: str = "mistral-large-4-0"
    mistral_draft_model: str = "mistral-small-2603"
    mistral_embedding_model: str = "mistral-embed-2312"
    # Large 4 always thinks; this pins how much (low, medium or high), so every eval run uses the same setting
    mistral_reasoning_effort: str = "low"
    claude_comparison_model: str = "claude-haiku-5-5"
    # The answer judge: another model family than the answer model, to avoid self-preference bias
    claude_judge_model: str = "claude-sonnet-5-5"

    # Which bot answers /chat: the stub (a fixed answer, no API calls) unless .env says real (record 0035)
    rules_bot: Literal["stub", "real"] = "stub"

    # A key line left as "MISTRAL_API_KEY=" in .env arrives as an empty string: treat it as missing
    @field_validator("mistral_api_key")
    @classmethod
    def reject_empty_key(cls, key: SecretStr) -> SecretStr:
        if not key.get_secret_value().strip():
            raise ValueError("the key is empty")
        return key

    # The optional key left as "ANTHROPIC_API_KEY=" counts as not set, so the app still starts
    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def treat_empty_key_as_missing(cls, key: str | None) -> str | None:
        if key is not None and not key.strip():
            return None
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


# Return the Anthropic key, or stop with a message that says who needs it and where to put it
def require_anthropic_api_key(settings: Settings) -> str:
    if settings.anthropic_api_key is None:
        raise MissingSettingError(
            "Missing setting: ANTHROPIC_API_KEY. Only the answer judge and the experiment runs need it. "
            "Paste your Anthropic key into .env after ANTHROPIC_API_KEY=."
        )
    return settings.anthropic_api_key.get_secret_value()
