"""Tests slice 5's two calls with a stub client that replays scripted replies, so no test calls the API."""

import json
from types import SimpleNamespace

from answer_flows.gather_then_write.gather_then_write import gather_then_write
from answer_flows.shared.rule_tools import RuleTools
from answer_flows.gather_then_write.answer_shape import GatheredAnswer, WrittenAnswer
from answer_flows.gather_then_write.gather_and_write_rules import GATHER_RULES, WRITE_RULES
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
WRITE_REPLY = json.dumps({"sentences": [{"is_gap": False, "text": "The posts are 1.55 m tall [1]."},
                                         {"is_gap": True, "text": "The rules don't say the highest string tension."}]})


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
    return gather_then_write(client, "test-model", "low", GATHER_RULES, QUESTION, STARTING_ITEMS, RULE_TOOLS)


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
    assert f"[1] {CHUNK_BY_ID['laws-1.4']['text']}" in write_input
    assert "Nothing gives a tension" not in write_input

    # Code builds the answer from both calls
    assert reply.answer.answer == "The posts are 1.55 m tall [1]. The rules don't say the highest string tension."
    assert reply.answer.citations[0].quote == CHUNK_BY_ID["laws-1.4"]["text"]


def test_the_reply_keeps_the_gathered_parts_and_the_raw_write_reply():
    """Record 0027: every answer line saves the gather call's parts and the write call's raw reply."""
    reply = run_flow(StubTwoCallClient(GATHER_REPLY))
    assert reply.gathered_parts == json.loads(GATHER_REPLY)["parts"]
    assert reply.write_reply == WRITE_REPLY
    assert reply.raw_reply == GATHER_REPLY


def test_no_answered_part_is_refused_by_code_with_no_write_call():
    client = StubTwoCallClient(REFUSAL_GATHER_REPLY)
    reply = run_flow(client)
    assert reply.answer.refused
    assert not reply.write_called
    assert reply.write_reply is None
    assert reply.gathered_parts == json.loads(REFUSAL_GATHER_REPLY)["parts"]
    assert len(client.requests) == 1


def test_a_gather_reply_that_does_not_fit_the_shape_is_a_format_error_with_no_write_call():
    client = StubTwoCallClient('{"reasoning": "cut off')
    reply = run_flow(client)
    assert reply.is_format_error
    assert reply.error_message.startswith("gather call, finish reason stop")
    assert len(client.requests) == 1


def test_a_write_reply_with_no_sentence_is_a_format_error():
    client = StubTwoCallClient(GATHER_REPLY, write_reply=json.dumps({"sentences": []}))
    reply = run_flow(client)
    assert reply.is_format_error
    assert reply.error_message == "write call: no sentences"


def test_write_rules_ask_for_a_related_sentence_only_when_it_completes_the_answer():
    assert "Add a related sentence when it completes the answer" in WRITE_RULES


def test_write_rules_answer_a_named_format_first():
    """A question that names a format gets that format's rule first. 17 Nov: "the standard rule doesn't apply" with no
    sentence saying so failed grounded (best-of-five-at-10-all, 3 of 3 runs), so the claim needs a sentence behind it."""
    assert "When the question names a format, answer from that format's rule first" in WRITE_RULES
    assert "never write that a rule doesn't apply unless a sentence says so" in WRITE_RULES
    assert "mention the standard rule only to say it doesn't apply there" not in WRITE_RULES
    assert "give the standard rule first, then name the format" in WRITE_RULES
