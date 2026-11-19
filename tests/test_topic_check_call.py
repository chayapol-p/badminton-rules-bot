"""
Tests for the real topic check (docs/specs/refuse-off-topic-questions-fast.md): one Mistral Small call
that answers whether a question is about the rules of badminton, with a 5 s limit and no retries, and a bot that lets
the question through when the call fails.

A recording client stands in for Mistral, so no test calls the API.
"""

import logging
from types import SimpleNamespace

import pytest

from answer_flows import rules_bot as rules_bot_module
from answer_flows.topic_screen import (CHECK_TIMEOUT_MS, TOPIC_CHECK_PROMPT, build_mistral_topic_check)
from settings import Settings
from tests.test_gather_then_write import GATHER_REPLY, StubTwoCallClient
from tests.test_rules_bot import CHUNKS, NEW_QUESTION, RULE_MAP, SETTINGS, StubSearch


# ===== Test helpers =====

class RecordingCheckClient:
    """Stub Mistral client for the check: records each request and answers with one fixed reply text,
    or raises the error it was given."""

    def __init__(self, reply_text: str = '{"is_badminton_question": true}', error: Exception | None = None):
        self.requests = []
        self.reply_text = reply_text
        self.error = error
        self.chat = SimpleNamespace(complete=self.complete)

    def complete(self, **request):
        """Records the request, then raises the error or returns the reply in the SDK's shape."""
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply_text))])


# Returns a bot whose topic check is the real check on the given client, and whose flow runs on a stub client
def build_bot_with_real_check(check_client: RecordingCheckClient) -> tuple[rules_bot_module.RulesBot, StubTwoCallClient]:
    flow_client = StubTwoCallClient(GATHER_REPLY)
    topic_check = build_mistral_topic_check(check_client, SETTINGS.mistral_draft_model)
    rules_bot = rules_bot_module.RulesBot(flow_client, SETTINGS, CHUNKS, RULE_MAP, StubSearch().search,
                                          is_rules_question=topic_check)
    return rules_bot, flow_client


# ===== The request =====

def test_the_check_sends_the_question_to_mistral_small_with_a_5_second_limit_and_no_retries():
    check_client = RecordingCheckClient()

    build_mistral_topic_check(check_client, SETTINGS.mistral_draft_model)("what is tennis")

    request = check_client.requests[0]
    assert request["model"] == "mistral-small-2603"
    assert request["temperature"] == 0
    assert request["timeout_ms"] == CHECK_TIMEOUT_MS == 5_000
    assert request["retries"].strategy == "none"
    assert request["messages"] == [{"role": "system", "content": TOPIC_CHECK_PROMPT},
                                   {"role": "user", "content": "what is tennis"}]


def test_the_prompt_follows_jobs_picks_for_what_counts_as_off_topic():
    # Badminton-wide: any badminton question goes on, however it is worded, and only one with nothing
    # to do with badminton is off topic; a doubt goes to the full flow, so no rules question is refused by mistake
    for words in ["any question about badminton", "coaching", "history", "not about badminton at all",
                  "another sport on its own", "casual", "even when they do not name the sport",
                  "Short questions about play, scoring",
                  "When unsure, answer true"]:
        assert words in TOPIC_CHECK_PROMPT


# ===== The reply =====

def test_a_no_reply_calls_the_question_off_topic():
    check_client = RecordingCheckClient('{"is_badminton_question": false}')

    assert not build_mistral_topic_check(check_client, SETTINGS.mistral_draft_model)("what is tennis")


def test_a_yes_reply_calls_the_question_a_rules_question():
    check_client = RecordingCheckClient('{"is_badminton_question": true}')

    assert build_mistral_topic_check(check_client, SETTINGS.mistral_draft_model)("can i serve overhead lol")


@pytest.mark.parametrize("reply_text", ["yes", '{"answer": "no"}', '{"is_badminton_question": "maybe"}'])
def test_a_reply_outside_the_shape_lets_the_question_through_to_the_full_flow(reply_text):
    rules_bot, flow_client = build_bot_with_real_check(RecordingCheckClient(reply_text))

    rules_answer = rules_bot.answer(NEW_QUESTION)

    assert not rules_answer.refused
    assert len(flow_client.requests) == 2


# ===== A failed call (criterion 5) =====

def test_a_timeout_lets_the_question_through_and_is_logged(caplog):
    rules_bot, flow_client = build_bot_with_real_check(RecordingCheckClient(error=TimeoutError("no reply in 5 s")))

    with caplog.at_level(logging.WARNING):
        rules_answer = rules_bot.answer(NEW_QUESTION)

    assert not rules_answer.refused
    assert len(flow_client.requests) == 2
    assert "no reply in 5 s" in caplog.text


def test_an_off_topic_reply_from_the_real_check_gives_the_off_topic_answer_without_the_flow():
    rules_bot, flow_client = build_bot_with_real_check(RecordingCheckClient('{"is_badminton_question": false}'))

    rules_answer = rules_bot.answer("what is tennis")

    assert rules_answer.refusal_kind == "off_topic"
    assert flow_client.requests == []


# ===== Wiring =====

def test_load_rules_bot_wires_in_the_real_check_on_the_settings_model(monkeypatch):
    check_client = RecordingCheckClient('{"is_badminton_question": false}')
    monkeypatch.setattr(rules_bot_module, "build_mistral_client", lambda settings: check_client)
    monkeypatch.setattr(rules_bot_module, "load_settings",
                        lambda: Settings(_env_file=None, mistral_api_key="test-api-key", anthropic_api_key="test-api-key"))

    loaded_bot = rules_bot_module.load_rules_bot()

    assert not loaded_bot.is_rules_question("what is tennis")
    assert check_client.requests[0]["model"] == "mistral-small-2603"
