"""
Asks Mistral for one answer in the RulesAnswer shape, and returns it with the tokens it used.

Fixed for every eval run (experiment rule 2): the pinned model from app/settings.py and
temperature 0. The call sends RulesAnswer as a strict JSON schema, then parses the reply here,
not inside the SDK, so a reply that doesn't fit the shape still reports the tokens it cost.
Such a reply comes back flagged as a format error, with the validation message and the raw
text, and the run records it instead of stopping. Network and API errors still stop the run;
retries come in Stage 4.

Use:
    reply = answer_question(client, model, question_text, retrieved_chunks)
"""

from dataclasses import dataclass

from mistralai.client import Mistral
from mistralai.extra import response_format_from_pydantic_model
from pydantic import ValidationError

from answer.answer_shape import RulesAnswer
from answer.build_answer_prompt import build_answer_messages


# Constants
## An upper bound on the answer's length, so one runaway reply can't run up the bill
MAX_ANSWER_TOKENS = 1024


# ===== The reply =====

@dataclass
class AnswerReply:
    """One answer, or a format error with its message and raw text, plus the tokens the call used either way."""

    answer: RulesAnswer | None
    is_format_error: bool
    error_message: str | None
    raw_reply: str
    input_tokens: int
    output_tokens: int


# ===== One answer =====

def answer_question(client: Mistral, model: str, question_text: str, retrieved_chunks: list[dict]) -> AnswerReply:
    """Returns the model's answer to one question, written only from the retrieved chunks."""

    # Ask with the RulesAnswer schema, the same strict schema chat.parse would send
    response = client.chat.complete(
        model=model,
        messages=build_answer_messages(question_text, retrieved_chunks),
        response_format=response_format_from_pydantic_model(RulesAnswer),
        temperature=0,
        max_tokens=MAX_ANSWER_TOKENS,
    )
    choice = response.choices[0]
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens

    # A reply cut off at the token limit, or with no text, can't fit the shape: keep its finish reason in the message
    raw_reply = choice.message.content
    if raw_reply is None:
        raw_reply = ""

    # Parse here, so a bad reply still reports its tokens
    try:
        rules_answer = RulesAnswer.model_validate_json(raw_reply)
    except ValidationError as error:
        return AnswerReply(
            answer=None,
            is_format_error=True,
            error_message=f"finish reason {choice.finish_reason}: {error}",
            raw_reply=raw_reply,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    return AnswerReply(
        answer=rules_answer,
        is_format_error=False,
        error_message=None,
        raw_reply=raw_reply,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
