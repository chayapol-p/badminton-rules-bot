"""
Tests the Mistral answer call with a stub client, so no test ever calls the API.
"""

import json
from types import SimpleNamespace

from answer.answer_with_mistral import answer_question
from tests.sample_data import SAMPLE_CHUNKS


# ===== A stub client that answers with fixed text =====

class StubChatClient:
    """Stub: answers every request with the given text and token counts, and records the request."""

    def __init__(self, reply_text: str | None, finish_reason: str = "stop"):
        self.reply_text = reply_text
        self.finish_reason = finish_reason
        self.requests = []
        self.chat = SimpleNamespace(complete=self.complete)

    def complete(self, **request):
        self.requests.append(request)
        message = SimpleNamespace(content=self.reply_text)
        choice = SimpleNamespace(message=message, finish_reason=self.finish_reason)
        usage = SimpleNamespace(prompt_tokens=900, completion_tokens=60)
        return SimpleNamespace(choices=[choice], usage=usage)


## A reply in the RulesAnswer shape
GOOD_REPLY_TEXT = json.dumps({
    "reasoning": "Law 1.4 gives the posts' height.",
    "refused": False,
    "answer": "1.55 metres.",
    "citations": [{"chunk_id": "laws-1.4", "quote": "The posts shall be 1.55 metres in height"}],
})


# ===== Tests =====

def test_a_reply_in_the_shape_is_parsed():
    reply = answer_question(StubChatClient(GOOD_REPLY_TEXT), "test-model", "How tall are the posts?", SAMPLE_CHUNKS)
    assert not reply.is_format_error
    assert reply.answer.citations[0].chunk_id == "laws-1.4"


def test_a_reply_cut_off_mid_json_is_a_format_error_that_keeps_its_tokens():
    reply = answer_question(StubChatClient(GOOD_REPLY_TEXT[:40], finish_reason="length"), "test-model",
                            "How tall are the posts?", SAMPLE_CHUNKS)
    assert reply.is_format_error
    assert reply.answer is None
    assert reply.error_message.startswith("finish reason length")
    assert reply.raw_reply == GOOD_REPLY_TEXT[:40]
    assert (reply.input_tokens, reply.output_tokens) == (900, 60)


def test_a_reply_with_no_text_is_a_format_error():
    reply = answer_question(StubChatClient(None), "test-model", "How tall are the posts?", SAMPLE_CHUNKS)
    assert reply.is_format_error
    assert reply.raw_reply == ""


def test_the_request_sends_the_strict_schema_at_temperature_0():
    client = StubChatClient(GOOD_REPLY_TEXT)
    answer_question(client, "test-model", "How tall are the posts?", SAMPLE_CHUNKS)
    request = client.requests[0]
    assert request["temperature"] == 0
    assert request["response_format"]["json_schema"]["strict"] is True
    assert list(request["response_format"]["json_schema"]["schema"]["properties"]) == ["reasoning", "refused", "answer", "citations"]
