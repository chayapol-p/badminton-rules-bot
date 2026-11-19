"""
Tests for POST /chat, slice 1 of docs/specs/ask-a-rules-question.md: a question goes in, and the answer comes back
as one server-sent event named "answer" (record 0031).

Until slice 4 the app answers with the stub bot, which returns the sample answer about the posts. No test calls
Mistral: the keys are placeholders.
"""

import json

import pytest
from fastapi.testclient import TestClient

from answer_flows.shared.answer_shape import RulesAnswer
from answer_flows.shared.cite_sentences import name_source
from app.chat_endpoint import get_rules_bot
from app.main import app
from app.stub_rules_bot import SAMPLE_POSTS_ANSWER, StubRulesBot
from retrieval.load_rule_chunks import load_chunks
from settings import load_settings


# Constants
QUESTION = "How tall are the posts?"


# Start every test with fresh settings, placeholder keys, and a stub that sends its steps without waiting;
# a test can still swap in another bot
@pytest.fixture(autouse=True)
def placeholder_keys(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    load_settings.cache_clear()
    app.dependency_overrides[get_rules_bot] = StubRulesBot
    yield
    load_settings.cache_clear()
    app.dependency_overrides.clear()


# Read a server-sent events body into (event name, data) pairs, skipping comment-only blocks such as keep-alive pings
def read_events(body: str) -> list[tuple[str, str]]:
    events = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        event_name = "message"
        data_lines = []
        for line in block.splitlines():
            field_name, _, value = line.partition(":")
            if field_name == "event":
                event_name = value.strip()
            elif field_name == "data":
                data_lines.append(value.removeprefix(" "))
        if data_lines:
            events.append((event_name, "\n".join(data_lines)))
    return events


# A stub bot that also keeps every question it was asked
class QuestionRecordingBot(StubRulesBot):

    def __init__(self):
        super().__init__()
        self.questions_asked = []

    def answer(self, question_text: str, report_progress=None) -> RulesAnswer:
        self.questions_asked.append(question_text)
        return super().answer(question_text)


# Criterion 1: a question streams back exactly one "answer" event that holds the stub's answer, markers and citations
def test_a_question_streams_one_answer_event_with_the_stub_answer():
    with TestClient(app) as client:
        response = client.post("/chat", json={"question": QUESTION})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    # Since slice 2, progress events come first; the answer is the one and only "answer" event, at the end
    events = read_events(response.text)
    answer_events = [event_data for event_name, event_data in events if event_name == "answer"]
    assert len(answer_events) == 1
    assert events[-1][0] == "answer"
    answer = json.loads(answer_events[0])
    assert answer["answer_sentences"][0]["text"].endswith("[1].")
    assert answer["citations"][0]["source_name"] == "Laws of Badminton 5.0 (2), Clause 1.4"
    assert RulesAnswer.model_validate(answer) == SAMPLE_POSTS_ANSWER


# The question in the request body is the question the bot answers
def test_the_question_reaches_the_bot():
    recording_bot = QuestionRecordingBot()
    app.dependency_overrides[get_rules_bot] = lambda: recording_bot

    with TestClient(app) as client:
        client.post("/chat", json={"question": QUESTION})

    assert recording_bot.questions_asked == [QUESTION]


# The sample answer is a real sample: its quote is the clause text as printed, under the clause's own name
def test_the_sample_answer_quotes_the_real_clause():
    chunk_by_id = {chunk["id"]: chunk for chunk in load_chunks()}
    citation = SAMPLE_POSTS_ANSWER.citations[0]
    clause = chunk_by_id[citation.chunk_id]

    assert citation.quote == clause["text"]
    assert citation.source_name == name_source(clause)
