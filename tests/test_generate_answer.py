"""
Tests the Mistral answer call with a stub client, so no test ever calls the API.
"""

import json
from types import SimpleNamespace

from mistralai.client.models import TextChunk, ThinkChunk

from answer.generate_answer import generate_answer
from tests.sample_data import SAMPLE_CHUNKS


# ===== A stub client that answers with fixed text =====

class StubChatClient:
    """Stub: answers every request with the given text and token counts, and records the request."""

    def __init__(self, reply_text: str | list | None, finish_reason: str = "stop"):
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
    reply = generate_answer(StubChatClient(GOOD_REPLY_TEXT), "test-model", "low", "How tall are the posts?", SAMPLE_CHUNKS)
    assert not reply.is_format_error
    assert reply.answer.citations[0].chunk_id == "laws-1.4"


def test_a_reply_cut_off_mid_json_is_a_format_error_that_keeps_its_tokens():
    reply = generate_answer(StubChatClient(GOOD_REPLY_TEXT[:40], finish_reason="length"), "test-model", "low",
                            "How tall are the posts?", SAMPLE_CHUNKS)
    assert reply.is_format_error
    assert reply.answer is None
    assert reply.error_message.startswith("finish reason length")
    assert reply.raw_reply == GOOD_REPLY_TEXT[:40]
    assert (reply.input_tokens, reply.output_tokens) == (900, 60)


def test_a_reply_with_no_text_is_a_format_error():
    reply = generate_answer(StubChatClient(None), "test-model", "low", "How tall are the posts?", SAMPLE_CHUNKS)
    assert reply.is_format_error
    assert reply.raw_reply == ""


def test_the_request_sends_the_strict_schema_with_greedy_sampling():
    client = StubChatClient(GOOD_REPLY_TEXT)
    generate_answer(client, "test-model", "low", "How tall are the posts?", SAMPLE_CHUNKS)
    request = client.requests[0]
    assert request["temperature"] == 0
    assert request["top_p"] == 1, "Mistral rejects temperature 0 unless top_p is 1"
    assert request["reasoning_effort"] == "low"
    assert request["response_format"]["json_schema"]["strict"] is True
    assert list(request["response_format"]["json_schema"]["schema"]["properties"]) == ["reasoning", "refused", "answer", "citations"]


def test_a_reply_in_chunks_is_parsed_and_its_thinking_kept():
    """Large 4 sends thinking chunks, then the answer in text chunks, never plain text."""
    chunks = [
        ThinkChunk(thinking=[TextChunk(text="The posts question. "), TextChunk(text="Law 1.4 has it.")]),
        TextChunk(text=GOOD_REPLY_TEXT),
    ]
    reply = generate_answer(StubChatClient(chunks), "test-model", "low", "How tall are the posts?", SAMPLE_CHUNKS)
    assert not reply.is_format_error
    assert reply.answer.answer == "1.55 metres."
    assert reply.thinking == "The posts question. Law 1.4 has it."
    assert reply.raw_reply == GOOD_REPLY_TEXT
