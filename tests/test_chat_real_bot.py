"""
Tests for POST /chat: the RULES_BOT setting picks the stub or the real bot, the bot loads once at startup,
and a failed answer streams an "error" event (spec criterion 5, record 0035).

No test calls Mistral: the real bot's loader is swapped for one that returns a stub.
"""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from answer_flows.rules_bot import AnswerFormatError
from answer_flows.shared.progress_updates import ProgressUpdate, ReportProgress, ignore_progress
from app import chat_endpoint
from app.chat_endpoint import FAILED_ANSWER_MESSAGE, choose_rules_bot
from app.main import app
from app.stub_rules_bot import StubRulesBot
from settings import MissingSettingError, Settings, load_settings
from tests.rule_data import skip_without_rule_data
from tests.test_chat_endpoint import QuestionRecordingBot, placeholder_keys, read_events  # placeholder_keys runs here too


# ===== Test helpers =====

class FailingBot:
    """Sends one step, then fails the way the real bot can: with the error it was built with."""

    def __init__(self, error: Exception):
        self.error = error

    def answer(self, question_text: str, report_progress: ReportProgress = ignore_progress):
        report_progress(ProgressUpdate(step="finding_rules", message="Searching the rule books"))
        raise self.error


# Asks /chat one question with the given bot and returns its events as (event name, data) pairs
def ask_with_bot(rules_bot) -> list[tuple[str, str]]:
    app.dependency_overrides[chat_endpoint.get_rules_bot] = lambda: rules_bot
    with TestClient(app) as client:
        response = client.post("/chat", json={"question": "How tall are the posts?"})
    return read_events(response.text)


# ===== Picking the bot =====

def test_the_stub_answers_when_rules_bot_is_not_set():
    settings = Settings(_env_file=None, mistral_api_key="test-mistral-key", anthropic_api_key="test-anthropic-key")

    assert settings.rules_bot == "stub"
    assert isinstance(choose_rules_bot(settings), StubRulesBot)


def test_rules_bot_real_loads_the_real_bot_once_at_startup(monkeypatch):
    skip_without_rule_data()
    monkeypatch.setenv("RULES_BOT", "real")
    load_settings.cache_clear()
    loaded_bots = []

    # Stands in for load_rules_bot: hands out a recording stub, so nothing calls Mistral
    def load_recording_bot():
        loaded_bots.append(QuestionRecordingBot())
        return loaded_bots[-1]

    monkeypatch.setattr(chat_endpoint, "load_rules_bot", load_recording_bot)
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        client.post("/chat", json={"question": "How tall are the posts?"})
        client.post("/chat", json={"question": "How high is the net?"})

    assert len(loaded_bots) == 1
    assert loaded_bots[0].questions_asked == ["How tall are the posts?", "How high is the net?"]


def test_an_unknown_rules_bot_setting_stops_startup_naming_it(monkeypatch):
    monkeypatch.setenv("RULES_BOT", "live")

    with pytest.raises(MissingSettingError, match="RULES_BOT"):
        load_settings()


# ===== A failed answer =====

def test_a_bad_answer_streams_an_error_event_after_the_steps():
    events = ask_with_bot(FailingBot(AnswerFormatError("write call: the reply had no JSON")))

    assert [event_name for event_name, event_data in events] == ["progress", "error"]
    assert json.loads(events[-1][1]) == {"message": FAILED_ANSWER_MESSAGE}
    assert FAILED_ANSWER_MESSAGE == "Couldn't write a checked answer. Please try again."


def test_a_network_failure_streams_the_same_error_event():
    events = ask_with_bot(FailingBot(ConnectionError("Mistral did not answer")))

    assert [event_name for event_name, event_data in events] == ["progress", "error"]


def test_the_bot_error_is_logged_with_its_own_message(caplog):
    with caplog.at_level(logging.ERROR):
        ask_with_bot(FailingBot(AnswerFormatError("write call: the reply had no JSON")))

    assert "write call: the reply had no JSON" in caplog.text
