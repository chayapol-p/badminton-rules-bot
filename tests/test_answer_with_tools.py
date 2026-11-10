"""
Tests the agent loop with a stub client that replays scripted replies, so no test calls the API.

Most tests need the Stage 3, Step 3 blanks filled in agent/answer_with_tools.py.
"""

import hashlib
import json
from types import SimpleNamespace

from agent.answer_with_tools import (AGENT_RULES_VERSION_2, EXTRA_AGENT_RULES, LAST_ROUND_NOTE, LAST_ROUND_NOTE_VERSION_2,
                                     MAX_TOOL_ROUNDS, answer_with_tools, build_agent_prompt, has_reached_tool_limit)
from agent.rule_tools import SEARCH_QUERY_DESCRIPTION_VERSION_2, RuleTools
from answer.build_answer_prompt import ANSWER_RULES, build_answer_rules
from evals.golden_answer_chunks import load_chunks
from retrieval.expand_with_rule_links import load_rule_map


# ===== The stub client and the tools =====

CHUNKS = load_chunks()
CHUNK_BY_ID = {chunk["id"]: chunk for chunk in CHUNKS}

## A reply in the RulesAnswer shape, citing a clause the search below returns
ANSWER_TEXT = json.dumps({
    "reasoning": "Law 1.4 gives the posts' height.",
    "refused": False,
    "answer": "1.55 metres.",
    "citations": [{"chunk_id": "laws-1.4", "quote": "1.55 metres"}],
})


def posts_search(query: str, top_k: int) -> list[dict]:
    """Stub: returns Law 1.4, whatever the query."""
    return [CHUNK_BY_ID["laws-1.4"]]


RULE_TOOLS = RuleTools(CHUNKS, posts_search, load_rule_map())


def search_call(call_number: int) -> SimpleNamespace:
    """Returns one search_rules tool call, as the SDK hands it over."""
    function = SimpleNamespace(name="search_rules", arguments='{"query": "post height", "top_k": 5}')
    return SimpleNamespace(id=f"call-{call_number}", function=function)


class StubToolClient:
    """Stub: asks for one search per reply for the first tool_reply_count calls, then answers; answers at once when tools are turned off."""

    def __init__(self, tool_reply_count: int, final_finish_reason: str = "stop", ignores_tool_choice: bool = False):
        self.tool_reply_count = tool_reply_count
        self.final_finish_reason = final_finish_reason
        self.ignores_tool_choice = ignores_tool_choice
        self.requests = []
        self.chat = SimpleNamespace(complete=self.complete)

    def complete(self, **request):
        self.requests.append(request)
        call_number = len(self.requests)
        may_ask_for_tools = self.ignores_tool_choice or request["tool_choice"] == "auto"
        asks_for_tools = call_number <= self.tool_reply_count and may_ask_for_tools
        if asks_for_tools:
            message = SimpleNamespace(role="assistant", content="", tool_calls=[search_call(call_number)])
            finish_reason = "tool_calls"
        else:
            message = SimpleNamespace(role="assistant", content=ANSWER_TEXT, tool_calls=None)
            finish_reason = self.final_finish_reason
        choice = SimpleNamespace(message=message, finish_reason=finish_reason)
        usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=100)
        return SimpleNamespace(choices=[choice], usage=usage)


def run_agent(client: StubToolClient, starting_chunks: list[dict] | None = None):
    """Runs the loop on one question with the stub client."""
    return answer_with_tools(client, "test-model", "low", ANSWER_RULES, "How tall are the posts?",
                             starting_chunks or [], RULE_TOOLS)


# ===== The prompt (given code) =====

def test_an_extra_agent_rule_is_added_to_the_agent_rules_only_when_named():
    plain_messages = build_agent_prompt(ANSWER_RULES, "How tall are the posts?", [])
    ruled_messages = build_agent_prompt(ANSWER_RULES, "How tall are the posts?", [], ["check-each-part"])
    assert EXTRA_AGENT_RULES["check-each-part"] not in plain_messages[0]["content"]
    assert ruled_messages[0]["content"].endswith("- " + EXTRA_AGENT_RULES["check-each-part"])


def test_setup_b_starts_with_the_question_only_and_setup_c_with_sources():
    agentic_messages = build_agent_prompt(ANSWER_RULES, "How tall are the posts?", [])
    hybrid_messages = build_agent_prompt(ANSWER_RULES, "How tall are the posts?", [CHUNK_BY_ID["laws-1.4"]])
    assert "No sources yet" in agentic_messages[1]["content"]
    assert "[laws-1.4]" in hybrid_messages[1]["content"]
    assert "Tools:" in agentic_messages[0]["content"]


# ===== Prompt versions (Stage 3) =====

## sha256 of version 1's system messages and last-round note, taken at commit 123e484 before version 2 was
## added (10 Nov 2026): no extra rules, and both extra rules of the current best C
VERSION_1_SYSTEM_SHA256 = "ac3fc298d3ab1995ddcff71e7d06bdf7beb4b94a5cb11cedd250ab3f133a39f0"
VERSION_1_BEST_C_SYSTEM_SHA256 = "b07fb28bdbe4a306e1c3294efd3cca2b5dc9e7bfe4b7514fb7b8fc8d583d3345"
VERSION_1_LAST_ROUND_NOTE_SHA256 = "94f5bf378d131bb740bd14706985018f6e72adf448f8a0bfbfb1b57f07d6a4da"


def sha256_of(text: str) -> str:
    """Returns the sha256 of a text, as hex."""
    return hashlib.sha256(text.encode()).hexdigest()


def system_message(prompt_version: int, extra_agent_rule_names: list[str] | None = None) -> str:
    """Returns the agent's system message for a prompt version, with no starting sources."""
    answer_rules = build_answer_rules([], prompt_version)
    messages = build_agent_prompt(answer_rules, "How tall are the posts?", [], extra_agent_rule_names, prompt_version)
    return messages[0]["content"]


def test_version_1_builds_exactly_the_agent_prompt_of_every_earlier_run():
    assert sha256_of(system_message(1)) == VERSION_1_SYSTEM_SHA256
    assert sha256_of(system_message(1, ["check-each-part", "search-before-gaps"])) == VERSION_1_BEST_C_SYSTEM_SHA256
    assert sha256_of(LAST_ROUND_NOTE) == VERSION_1_LAST_ROUND_NOTE_SHA256


def test_version_2_replaces_the_agent_rules_and_folds_in_both_extra_rules():
    version_2_message = system_message(2)
    assert version_2_message.endswith(AGENT_RULES_VERSION_2)
    assert "When the sources already answer the question" not in version_2_message, "version 1's bullets are gone"
    for extra_rule_text in EXTRA_AGENT_RULES.values():
        assert extra_rule_text not in version_2_message
    assert "Mark a part \"none\" only after its searches found nothing." in version_2_message
    assert "never mention tools, searches, or which documents you checked" in version_2_message


def test_version_2_ignores_extra_agent_rules_handed_to_the_prompt():
    """The run script refuses the pair; the prompt itself never adds them to version 2."""
    assert system_message(2, ["check-each-part"]) == system_message(2)


def test_version_2_sends_its_last_round_note_and_its_tool_text():
    client = StubToolClient(tool_reply_count=100)
    answer_with_tools(client, "test-model", "low", build_answer_rules([], 2), "How tall are the posts?", [], RULE_TOOLS,
                      prompt_version=2)
    last_tool_message = client.requests[-1]["messages"][-1]
    assert last_tool_message["content"].endswith(LAST_ROUND_NOTE_VERSION_2)
    assert LAST_ROUND_NOTE not in last_tool_message["content"]
    query_definition = client.requests[0]["tools"][0]["function"]["parameters"]["properties"]["query"]
    assert query_definition["description"] == SEARCH_QUERY_DESCRIPTION_VERSION_2


# ===== The round limit (Step 3) =====

def test_the_limit_is_reached_at_round_10_and_stays_reached_past_it():
    assert not has_reached_tool_limit(MAX_TOOL_ROUNDS - 1)
    assert has_reached_tool_limit(MAX_TOOL_ROUNDS)
    assert has_reached_tool_limit(MAX_TOOL_ROUNDS + 1)


# ===== The loop (Step 3) =====

def test_a_reply_with_no_tool_calls_is_the_answer():
    client = StubToolClient(tool_reply_count=0)
    reply = run_agent(client, [CHUNK_BY_ID["laws-1.4"]])
    assert not reply.is_format_error
    assert (reply.tool_rounds, reply.model_calls) == (0, 1)
    assert (reply.input_tokens, reply.output_tokens) == (1000, 100)


def test_one_round_runs_the_tool_and_answers_from_what_it_showed():
    client = StubToolClient(tool_reply_count=1)
    reply = run_agent(client)
    assert (reply.tool_rounds, reply.model_calls) == (1, 2)
    assert [chunk["id"] for chunk in reply.shown_chunks] == ["laws-1.4"]

    # The second call carries the model's call, then the tool result matched to it by id
    second_request_messages = client.requests[1]["messages"]
    assert second_request_messages[-1]["role"] == "tool"
    assert second_request_messages[-1]["tool_call_id"] == "call-1"
    assert second_request_messages[-2].tool_calls[0].id == "call-1", "the model's own message comes before its tool results"
    assert "[laws-1.4]" in second_request_messages[-1]["content"]
    assert reply.tool_calls[0]["shown_ids"] == ["laws-1.4"]
    assert reply.tool_calls[0]["round"] == 1, "the first round is round 1"
    assert not reply.tools_turned_off
    assert LAST_ROUND_NOTE not in second_request_messages[-1]["content"]


def test_after_round_10_the_last_result_carries_the_note_and_the_next_call_can_only_answer():
    client = StubToolClient(tool_reply_count=100)
    reply = run_agent(client)
    assert reply.tool_rounds == MAX_TOOL_ROUNDS
    last_tool_message = client.requests[-1]["messages"][-1]
    assert last_tool_message["content"].endswith(LAST_ROUND_NOTE)
    assert "[laws-1.4]" in last_tool_message["content"], "the last round's tools still run"
    assert client.requests[-1]["tool_choice"] == "none"
    assert reply.model_calls == MAX_TOOL_ROUNDS + 1
    assert reply.tools_turned_off
    assert not reply.is_format_error


def test_a_reply_with_tool_calls_after_the_tools_are_off_still_ends_the_loop():
    """tool_choice "none" should stop tool calls; if the API ever sends one anyway, the loop must not run it."""
    client = StubToolClient(tool_reply_count=100, ignores_tool_choice=True)
    reply = run_agent(client)
    assert reply.tool_rounds == MAX_TOOL_ROUNDS
    assert reply.model_calls == MAX_TOOL_ROUNDS + 1
    assert reply.is_format_error


def test_a_reply_cut_off_at_the_token_cap_is_a_format_error():
    client = StubToolClient(tool_reply_count=0, final_finish_reason="length")
    client.chat = SimpleNamespace(complete=lambda **request: cut_off_reply())
    reply = run_agent(client)
    assert reply.is_format_error
    assert reply.error_message.startswith("finish reason length")


def test_a_tool_reply_with_no_tool_calls_is_a_format_error_not_a_crash():
    client = StubToolClient(tool_reply_count=0)
    client.chat = SimpleNamespace(complete=lambda **request: empty_tool_reply())
    reply = run_agent(client)
    assert reply.is_format_error
    assert reply.error_message.startswith("finish reason tool_calls")
    assert (reply.tool_rounds, reply.model_calls) == (0, 1)


def empty_tool_reply() -> SimpleNamespace:
    """Returns a reply whose finish reason says "tool_calls" but which holds no tool calls."""
    message = SimpleNamespace(role="assistant", content="", tool_calls=[])
    choice = SimpleNamespace(message=message, finish_reason="tool_calls")
    return SimpleNamespace(choices=[choice], usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=100))


def cut_off_reply() -> SimpleNamespace:
    """Returns a reply cut off mid-JSON by the token cap."""
    message = SimpleNamespace(role="assistant", content=ANSWER_TEXT[:40], tool_calls=None)
    choice = SimpleNamespace(message=message, finish_reason="length")
    return SimpleNamespace(choices=[choice], usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=100))
