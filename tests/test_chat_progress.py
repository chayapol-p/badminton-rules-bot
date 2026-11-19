"""
Tests for POST /chat: progress updates stream before the answer (spec criterion 2, record 0028).
Nothing here runs a paid API.
"""

import threading

import pytest
from fastapi.testclient import TestClient

from answer_flows.shared.progress_updates import ProgressUpdate, ReportProgress, ignore_progress
from app.chat_endpoint import get_rules_bot
from app.main import app
from app.stub_rules_bot import SAMPLE_POSTS_ANSWER, STUB_PROGRESS_UPDATES, StubRulesBot
from tests.rule_data import skip_without_rule_data
from tests.test_chat_endpoint import placeholder_keys, read_events  # placeholder_keys runs for every test here too


# ===== Test helpers =====

class StillWritingBot:
    """Sends one update from the calling thread and one from a second thread, like the "still writing" ticks."""

    def answer(self, question_text: str, report_progress: ReportProgress = ignore_progress):
        report_progress(ProgressUpdate(step="writing", message="Writing the answer"))
        ticker = threading.Thread(
            target=report_progress,
            args=[ProgressUpdate(step="still_writing", message="Still writing the answer · 5 s")])
        ticker.start()
        ticker.join()
        return SAMPLE_POSTS_ANSWER


# A test client for the app; clears any bot swapped in by the test
@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


# Asks /chat one question and returns its events as (event name, data) pairs
def ask(client: TestClient, question_text: str) -> list[tuple[str, str]]:
    response = client.post("/chat", json={"question": question_text})
    return read_events(response.text)


# ===== Order of events =====

def test_progress_events_come_before_the_answer(client):
    skip_without_rule_data()
    app.dependency_overrides[get_rules_bot] = StubRulesBot

    events = ask(client, "How tall are the posts?")

    event_names = [event_name for event_name, event_data in events]
    assert event_names == ["progress"] * len(STUB_PROGRESS_UPDATES) + ["answer"]


def test_each_progress_event_carries_the_update_as_json(client):
    skip_without_rule_data()
    app.dependency_overrides[get_rules_bot] = StubRulesBot

    events = ask(client, "How tall are the posts?")

    first_update = ProgressUpdate.model_validate_json(events[0][1])
    assert first_update.step == "finding_rules"
    assert first_update.message == "Searching the rule books"


# ===== Updates from another thread (record 0028: the "still writing" ticks) =====

def test_updates_sent_from_a_second_thread_reach_the_stream(client):
    skip_without_rule_data()
    app.dependency_overrides[get_rules_bot] = StillWritingBot

    events = ask(client, "How tall are the posts?")

    messages = [ProgressUpdate.model_validate_json(event_data).message
                for event_name, event_data in events if event_name == "progress"]
    assert messages == ["Writing the answer", "Still writing the answer · 5 s"]
    assert events[-1][0] == "answer"
