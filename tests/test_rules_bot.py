"""Tests the product entry point with a stub client and a stub search, so no test calls the API."""

import json

import pytest

from answer_flows.rules_bot import AnswerFormatError, RulesBot
from answer_flows.shared.rule_tools import RuleTools
from app.settings import Settings
from evals.golden_answer_chunks import load_chunks
from retrieval.expand_with_rule_links import load_rule_map
from tests.test_gather_then_write import GATHER_REPLY, REFUSAL_GATHER_REPLY, StubTwoCallClient


# Constants
## The clauses, the rule map and the settings every test shares; the keys are placeholders, never used
CHUNKS = load_chunks()
CHUNK_BY_ID = {chunk["id"]: chunk for chunk in CHUNKS}
RULE_MAP = load_rule_map()
SETTINGS = Settings(mistral_api_key="test-api-key", anthropic_api_key="test-api-key")

## A question no saved vector exists for, as an app user would ask it
NEW_QUESTION = "How high do the net posts have to be?"


# ===== Helpers =====

class StubSearch:
    """Stub: returns Law 1.4 for every query, and records each query it was asked."""

    def __init__(self):
        self.queries = []

    def search(self, query: str, top_k: int) -> list[dict]:
        """Records the query and returns Law 1.4."""
        self.queries.append(query)
        return [CHUNK_BY_ID["laws-1.4"]]


def build_bot(client: StubTwoCallClient, stub_search: StubSearch) -> RulesBot:
    """Returns a RulesBot that uses the stub client and the stub search."""
    return RulesBot(client, SETTINGS, CHUNKS, RULE_MAP, stub_search.search)


# ===== Answers =====

def test_a_new_question_gets_a_natural_answer_with_markers_and_quoted_sources():
    stub_search = StubSearch()
    rules_answer = build_bot(StubTwoCallClient(GATHER_REPLY), stub_search).answer(NEW_QUESTION)

    # The retrieve step searched with the question's own words, so no saved vector is needed
    assert stub_search.queries[0] == NEW_QUESTION

    # The answer comes sentence by sentence, and marker [1] points to Law 1.4's quote
    assert not rules_answer.refused
    assert rules_answer.answer_sentences[0].text == "The posts are 1.55 m tall [1]."
    assert rules_answer.answer_sentences[1].is_gap
    assert rules_answer.citations[0].chunk_id == "laws-1.4"
    assert rules_answer.citations[0].quote == CHUNK_BY_ID["laws-1.4"]["text"]


def test_the_bot_runs_the_product_flow_on_the_settings_model():
    client = StubTwoCallClient(GATHER_REPLY)
    build_bot(client, StubSearch()).answer(NEW_QUESTION)
    gather_request, write_request = client.requests
    assert gather_request["model"] == SETTINGS.mistral_answer_model
    assert write_request["reasoning_effort"] == SETTINGS.mistral_reasoning_effort
    assert "tools" in gather_request


def test_a_question_the_sources_do_not_answer_is_refused():
    client = StubTwoCallClient(REFUSAL_GATHER_REPLY)
    rules_answer = build_bot(client, StubSearch()).answer(NEW_QUESTION)
    assert rules_answer.refused
    assert len(client.requests) == 1


def test_each_question_gets_fresh_tools(monkeypatch):
    """The tools remember which clauses a question has seen, so sharing them would hide clauses from the next question."""
    built_tools = []

    class RecordingRuleTools(RuleTools):
        """RuleTools that records each one built."""

        def __init__(self, *arguments):
            super().__init__(*arguments)
            built_tools.append(self)

    monkeypatch.setattr("answer_flows.rules_bot.RuleTools", RecordingRuleTools)
    client = StubTwoCallClient(GATHER_REPLY)
    rules_bot = build_bot(client, StubSearch())
    rules_bot.answer(NEW_QUESTION)
    client.replies = client.replies * 2
    rules_bot.answer("And how tall are the posts in doubles?")
    assert len(built_tools) == 2
    assert built_tools[0] is not built_tools[1]


# ===== Failures =====

def test_a_reply_that_does_not_fit_the_shape_raises_and_names_the_call():
    client = StubTwoCallClient('{"reasoning": "cut off')
    with pytest.raises(AnswerFormatError, match="gather call, finish reason stop"):
        build_bot(client, StubSearch()).answer(NEW_QUESTION)


def test_a_write_reply_with_no_sentence_raises():
    client = StubTwoCallClient(GATHER_REPLY, write_reply=json.dumps({"sentences": []}))
    with pytest.raises(AnswerFormatError, match="write call: no sentences"):
        build_bot(client, StubSearch()).answer(NEW_QUESTION)
