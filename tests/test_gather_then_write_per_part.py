"""Tests the retired per-part slice 5's two calls with a stub client that replays scripted replies, so no test calls the API."""

import json
from types import SimpleNamespace

from experiments.retired_flows.gather_then_write_per_part.gather_then_write import gather_then_write_per_part
from answer_flows.shared.rule_tools import RuleTools
from experiments.retired_flows.gather_then_write_per_part.answer_shape import GatheredAnswer, WrittenAnswer
from experiments.retired_flows.gather_then_write_per_part.gather_and_write_rules import GATHER_RULES, WRITE_RULES
from evals.golden_answer_chunks import load_chunks
from retrieval.expand_with_rule_links import load_rule_map
from tests.sample_data import full_items


# ===== The stub client =====

CHUNKS = load_chunks()
CHUNK_BY_ID = {chunk["id"]: chunk for chunk in CHUNKS}
RULE_TOOLS = RuleTools(CHUNKS, lambda query, top_k: [CHUNK_BY_ID["laws-1.4"]], load_rule_map())
STARTING_ITEMS = full_items([CHUNK_BY_ID["laws-1.4"]])
QUESTION = "How tall are the posts, and what string tension is allowed?"

## The gather reply: part 1 answered by Law 1.4 sentence 1, part 2 with no sentence
GATHER_REPLY = json.dumps({
    "reasoning": "Law 1.4 gives the height. Nothing gives a tension.",
    "parts": [{"asks": "how tall the posts are", "sentences": [{"chunk_id": "laws-1.4", "sentence": 1}]},
              {"asks": "the highest string tension allowed", "sentences": []}],
    "related_sentences": [],
})
REFUSAL_GATHER_REPLY = json.dumps({
    "reasoning": "Nothing gives a tension.",
    "parts": [{"asks": "the highest string tension allowed", "sentences": []}],
    "related_sentences": [],
})
WRITE_REPLY = json.dumps({"answers": [{"part_number": 1, "answer": "1.55 metres (Laws of Badminton 5.0 (2))."}]})


class StubTwoCallClient:
    """Stub: answers the gather call with gather_reply (no tool calls) and the write call with write_reply."""

    def __init__(self, gather_reply: str, write_reply: str = WRITE_REPLY):
        self.replies = [gather_reply, write_reply]
        self.requests = []
        self.chat = SimpleNamespace(complete=self.complete)

    def complete(self, **request):
        self.requests.append(request)
        message = SimpleNamespace(role="assistant", content=self.replies[len(self.requests) - 1], tool_calls=None)
        choice = SimpleNamespace(message=message, finish_reason="stop")
        return SimpleNamespace(choices=[choice], usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=100))


def run_flow(client: StubTwoCallClient):
    """Runs both calls on one question with the stub client."""
    return gather_then_write_per_part(client, "test-model", "low", GATHER_RULES, QUESTION, STARTING_ITEMS, RULE_TOOLS)


# ===== The two calls =====

def test_an_answered_part_runs_the_write_call_with_no_tools_and_only_the_parts():
    client = StubTwoCallClient(GATHER_REPLY)
    reply = run_flow(client)
    assert not reply.is_format_error
    assert reply.write_called
    assert (reply.model_calls, reply.input_tokens) == (2, 2000)

    # The gather call has the tools and the gather shape; the write call has neither tools nor the reasoning
    gather_request, write_request = client.requests
    assert gather_request["response_format"]["json_schema"]["name"] == GatheredAnswer.__name__
    assert "tools" not in write_request
    assert write_request["response_format"]["json_schema"]["name"] == WrittenAnswer.__name__
    assert write_request["messages"][0]["content"] == WRITE_RULES
    write_input = write_request["messages"][1]["content"]
    assert "Part 2 · the highest string tension allowed\nNO SOURCE" in write_input
    assert "Nothing gives a tension" not in write_input

    # Code builds the answer from both calls
    assert reply.answer.answer.split("\n") == ["1.55 metres (Laws of Badminton 5.0 (2)).",
                                               "The sources do not say the highest string tension allowed."]
    assert reply.answer.citations[0].quote == CHUNK_BY_ID["laws-1.4"]["text"]


def test_no_answered_part_is_refused_by_code_with_no_write_call():
    client = StubTwoCallClient(REFUSAL_GATHER_REPLY)
    reply = run_flow(client)
    assert reply.answer.refused
    assert not reply.write_called
    assert len(client.requests) == 1


def test_a_gather_reply_that_does_not_fit_the_shape_is_a_format_error_with_no_write_call():
    client = StubTwoCallClient('{"reasoning": "cut off')
    reply = run_flow(client)
    assert reply.is_format_error
    assert reply.error_message.startswith("gather call, finish reason stop")
    assert len(client.requests) == 1


def test_a_write_reply_that_skips_an_answered_part_is_a_format_error():
    client = StubTwoCallClient(GATHER_REPLY, write_reply=json.dumps({"answers": []}))
    reply = run_flow(client)
    assert reply.is_format_error
    assert reply.error_message == "write call: no answer for parts [1]"


def test_write_rules_answer_a_named_format_first():
    """A question that names a format gets that format's rule first; the standard rule only to say it doesn't apply."""
    assert "When the question names a format, answer from that format's rule first" in WRITE_RULES
    assert "mention the standard rule only to say it doesn't apply there" in WRITE_RULES
    assert "give the standard rule first, then name the format" in WRITE_RULES
