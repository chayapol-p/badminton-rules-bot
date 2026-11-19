"""Tests the product entry point with a stub client and a stub search, so no test calls the API."""

import json
from types import SimpleNamespace

import pytest

from answer_flows.rules_bot import AnswerFormatError, RulesBot
from answer_flows.shared.progress_updates import (CHECKING_QUESTION, CHECKING_RULES, FINDING_RULES, FOUND_RULES, QUESTION_PARTS,
                                                  SEARCHING, SOURCES_PICKED, WRITING, ProgressUpdate)
from answer_flows.shared.rule_tools import RuleTools
from retrieval.expand_with_rule_links import load_rule_map
from retrieval.load_rule_chunks import load_chunks
from settings import Settings
from tests.rule_data import skip_without_rule_data
from tests.test_gather_then_write import GATHER_REPLY, REFUSAL_GATHER_REPLY, StubTwoCallClient


# Constants
## The clauses, the rule map and the settings every test shares; the keys are placeholders, never used
# Every test here reads the real clauses, built from the rule books and never committed
skip_without_rule_data()

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


# ===== Progress updates =====

class StubToolThenTwoCallClient(StubTwoCallClient):
    """Stub: the gather call first asks for one search, then sends gather_reply; the write call sends the write reply."""

    def __init__(self, gather_reply: str):
        super().__init__(gather_reply)
        self.replies = [None] + self.replies

    def complete(self, **request):
        """Replies with one search_rules call the first time, then as StubTwoCallClient."""
        if not self.requests:
            self.requests.append(request)
            function = SimpleNamespace(name="search_rules", arguments='{"query": "post height", "top_k": 5}')
            tool_call = SimpleNamespace(id="call-1", function=function, type="function")
            message = SimpleNamespace(role="assistant", content="", tool_calls=[tool_call])
            choice = SimpleNamespace(message=message, finish_reason="tool_calls")
            return SimpleNamespace(choices=[choice], usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=100))
        return super().complete(**request)


def collect_updates(client: StubTwoCallClient) -> list[ProgressUpdate]:
    """Answers NEW_QUESTION with the client and returns every progress update, in order."""
    updates = []
    build_bot(client, StubSearch()).answer(NEW_QUESTION, report_progress=updates.append)
    return updates


def test_an_answer_reports_each_step_and_the_quoted_sources_before_writing():
    updates = collect_updates(StubTwoCallClient(GATHER_REPLY))
    assert [update.step for update in updates] == [CHECKING_QUESTION, FINDING_RULES, FOUND_RULES, CHECKING_RULES,
                                                   QUESTION_PARTS, SOURCES_PICKED, WRITING]

    # The question's parts come at the gate, then the sources with their quotes, before the write call starts
    assert updates[4].message == ("Your question has 2 parts: how tall the posts are · "
                                  "the highest string tension allowed")
    sources_update = updates[5]
    assert sources_update.message == "Found 1 sentence that answers it"
    assert sources_update.sources[0].source_name == "Laws of Badminton 5.0 (2), Clause 1.4"
    assert sources_update.sources[0].quote in CHUNK_BY_ID["laws-1.4"]["text"]


def test_a_tool_round_reports_the_search_words_and_a_second_check():
    updates = collect_updates(StubToolThenTwoCallClient(GATHER_REPLY))
    assert [update.step for update in updates] == [CHECKING_QUESTION, FINDING_RULES, FOUND_RULES, CHECKING_RULES,
                                                   SEARCHING, CHECKING_RULES, QUESTION_PARTS, SOURCES_PICKED, WRITING]
    assert updates[4].message == 'Searching the rules: "post height"'
    assert updates[5].message == "Checking what the search found"


def test_a_refusal_reports_the_parts_but_no_sources_and_no_writing():
    updates = collect_updates(StubTwoCallClient(REFUSAL_GATHER_REPLY))
    assert [update.step for update in updates] == [CHECKING_QUESTION, FINDING_RULES, FOUND_RULES, CHECKING_RULES,
                                                   QUESTION_PARTS]
    assert updates[4].message == "Your question asks about the highest string tension allowed"
