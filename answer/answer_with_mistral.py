"""
Asks Mistral for one answer in the RulesAnswer shape, and returns it with the tokens it used.

Fixed for every eval run (experiment rule 2): the pinned model from app/settings.py and
temperature 0. An answer that doesn't fit the shape comes back as None, so the run records
a format error for that question instead of stopping. Network and API errors still stop the
run; retries come in Stage 4.

Use:
    reply = answer_question(client, model, question_text, retrieved_chunks)
"""

import json
from dataclasses import dataclass

from mistralai.client import Mistral
from pydantic import ValidationError

from answer.answer_shape import RulesAnswer
from answer.build_answer_prompt import build_answer_messages


# Constants
## An upper bound on the answer's length, so one runaway reply can't run up the bill
MAX_ANSWER_TOKENS = 1024


# ===== The reply =====

@dataclass
class AnswerReply:
    """One answer, or None when the reply didn't fit the shape, plus the tokens the call used."""

    answer: RulesAnswer | None
    input_tokens: int
    output_tokens: int


# ===== One answer =====

def answer_question(client: Mistral, model: str, question_text: str, retrieved_chunks: list[dict]) -> AnswerReply:
    """Returns the model's answer to one question, written only from the retrieved chunks."""
    messages = build_answer_messages(question_text, retrieved_chunks)

    # chat.parse sends RulesAnswer as a JSON schema, then parses the reply into a RulesAnswer.
    # A reply that isn't valid JSON, or misses a field, raises while parsing: count it as a format error
    try:
        response = client.chat.parse(
            response_format=RulesAnswer,
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=MAX_ANSWER_TOKENS,
        )
    except (json.JSONDecodeError, ValidationError):
        return AnswerReply(answer=None, input_tokens=0, output_tokens=0)

    parsed_answer = response.choices[0].message.parsed
    return AnswerReply(
        answer=parsed_answer,
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )
