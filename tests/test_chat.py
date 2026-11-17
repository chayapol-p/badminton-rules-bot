"""
Tests for the /chat endpoint (slice 1: the stub answer).

Test keys come from environment variables, which override .env, so these tests never
read or need your real keys — same pattern as test_settings_and_health.py.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.settings import load_settings


# Start every test with fresh settings and placeholder keys
@pytest.fixture(autouse=True)
def placeholder_keys(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    load_settings.cache_clear()
    yield
    load_settings.cache_clear()


# The stub answer has the wire shape: text with [n] markers, and a source list they all resolve into
def test_chat_returns_answer_with_numbered_sources():
    with TestClient(app) as client:
        response = client.post("/chat", json={"question": "How high can I serve?"})

    assert response.status_code == 200
    reply = response.json()
    assert isinstance(reply["answer"], str) and reply["answer"]

    sources = reply["sources"]
    assert [source["cite_no"] for source in sources] == list(range(1, len(sources) + 1))

    marker_numbers = [int(number) for number in re.findall(r"\[(\d+)\]", reply["answer"])]
    assert marker_numbers, "the answer carries at least one [n] marker"
    assert all(1 <= number <= len(sources) for number in marker_numbers)
    assert set(marker_numbers) == {source["cite_no"] for source in sources}, "every source is cited at least once"


# A missing, empty or whitespace-only question is rejected by validation
@pytest.mark.parametrize("payload", [{}, {"question": ""}, {"question": "   "}])
def test_chat_rejects_missing_or_blank_question(payload):
    with TestClient(app) as client:
        response = client.post("/chat", json=payload)

    assert response.status_code == 422


# /health keeps working next to the new endpoint
def test_health_still_answers():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
