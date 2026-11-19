"""
Tests for settings loading and the /health endpoint.

Test keys come from environment variables, which override .env, so these tests never
read or need your real keys. The test keys are placeholders: settings load them, but
nothing ever calls an API with them.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from settings import MissingSettingError, Settings, load_settings, require_anthropic_api_key


# Start every test with fresh settings and placeholder keys
@pytest.fixture(autouse=True)
def placeholder_keys(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()


# /health answers with the model names and never shows a key
def test_health_returns_models_without_keys():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["models"]["mistral_answer"] == "mistral-large-4-0"
    assert "test-mistral-key" not in response.text


# An empty key stops startup with a message naming the key and the fix
def test_empty_key_gives_clear_error(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "")

    with pytest.raises(MissingSettingError) as raised_error:
        load_settings()

    assert "MISTRAL_API_KEY" in str(raised_error.value)
    assert ".env.example" in str(raised_error.value)


# Hide the real .env, so a key saved there can't stand in for one a test leaves unset
@pytest.fixture
def no_env_file(monkeypatch):
    monkeypatch.setitem(Settings.model_config, "env_file", None)


# The app starts and /health answers with only the Mistral key set
def test_app_starts_without_anthropic_key(monkeypatch, no_env_file):
    monkeypatch.delenv("ANTHROPIC_API_KEY")

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert load_settings().anthropic_api_key is None


# An empty "ANTHROPIC_API_KEY=" line counts as not set, not as an error
def test_empty_anthropic_key_loads_as_none(monkeypatch, no_env_file):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    assert load_settings().anthropic_api_key is None


# The judge and the experiments stop with a clear message when the Anthropic key is missing
def test_require_anthropic_key_names_the_missing_key(monkeypatch, no_env_file):
    monkeypatch.delenv("ANTHROPIC_API_KEY")

    with pytest.raises(MissingSettingError) as raised_error:
        require_anthropic_api_key(load_settings())

    assert "ANTHROPIC_API_KEY" in str(raised_error.value)
    assert ".env" in str(raised_error.value)


# When the Anthropic key is set, require_anthropic_api_key returns it
def test_require_anthropic_key_returns_the_key():
    assert require_anthropic_api_key(load_settings()) == "test-anthropic-key"


# A missing Mistral key still stops startup
def test_missing_mistral_key_stops_startup(monkeypatch, no_env_file):
    monkeypatch.delenv("MISTRAL_API_KEY")

    with pytest.raises(MissingSettingError) as raised_error:
        load_settings()

    assert "MISTRAL_API_KEY" in str(raised_error.value)
