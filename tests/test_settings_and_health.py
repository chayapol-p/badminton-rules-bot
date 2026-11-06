"""
Tests for settings loading and the /health endpoint.

Fake keys come from environment variables, which override .env,
so these tests never read or need your real keys.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.settings import MissingSettingError, load_settings


# Start every test with fresh settings and fake keys
@pytest.fixture(autouse=True)
def fake_keys(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "fake-mistral-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()


# /health answers with the model names and never shows a key
def test_health_returns_models_without_keys():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["models"]["mistral_answer"] == "mistral-large-4-0"
    assert "fake-mistral-key" not in response.text


# An empty key stops startup with a message naming the key and the fix
def test_empty_key_gives_clear_error(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "")

    with pytest.raises(MissingSettingError) as raised_error:
        load_settings()

    assert "MISTRAL_API_KEY" in str(raised_error.value)
    assert ".env.example" in str(raised_error.value)
