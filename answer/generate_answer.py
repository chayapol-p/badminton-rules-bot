"""
Asks Mistral for one answer in the RulesAnswer shape, and returns it with the model's thinking and the tokens it used.

Fixed for every eval run (experiment rule 2): the pinned model and reasoning effort from
app/settings.py, and temperature 0. Mistral calls temperature 0 greedy sampling and rejects it
unless top_p is exactly 1 (400 error, code 3054), and the SDK sends no top_p of its own, so the
call sets both.

Mistral Large 4 always thinks before it answers, and sends its reply as a list of chunks: thinking
chunks, then text chunks with the answer (Mistral's reasoning docs: there is no plain-text mode).
The answer text is parsed into RulesAnswer; the thinking is kept as text for reading failures.

The reply is parsed here, not inside the SDK, so a reply that doesn't fit the shape still reports
the tokens it cost. Such a reply comes back flagged as a format error, with the validation message
and the raw text, and the run records it instead of stopping. Network and API errors still stop
the run; retries come in Stage 4.

Use:
    reply = generate_answer(client, model, reasoning_effort, answer_rules, question_text, retrieved_chunks)
"""

from dataclasses import dataclass

from mistralai.client import Mistral
from mistralai.client.models import TextChunk, ThinkChunk
from mistralai.extra import response_format_from_pydantic_model
from pydantic import ValidationError

from answer.answer_shape import RulesAnswer
from answer.build_answer_prompt import build_answer_prompt


# Constants
## An upper bound on the reply's length, thinking included, so one runaway reply can't run up the bill.
## Only used tokens are paid for. 4,096 cut off one long question in most runs on 8 Nov (red-card's
## thinking ran to about 3,500 tokens), so the cap is 16,000
MAX_ANSWER_TOKENS = 16_000


# ===== The reply =====

@dataclass
class AnswerReply:
    """One answer, or a format error with its message and raw text, plus the model's thinking and the tokens the call used."""

    answer: RulesAnswer | None
    is_format_error: bool
    error_message: str | None
    raw_reply: str
    thinking: str
    input_tokens: int
    output_tokens: int


# ===== Reading the reply's chunks =====

def split_reply_content(content: str | list | None) -> tuple[str, str]:
    """Returns the reply's answer text and its thinking text."""

    # Models that don't think send plain text; a reply with no content has neither part
    if content is None:
        return "", ""
    if isinstance(content, str):
        return content, ""

    # Large 4 sends thinking chunks, each holding text chunks, then text chunks with the answer
    answer_parts = []
    thinking_parts = []
    for chunk in content:
        if isinstance(chunk, ThinkChunk):
            for thinking_part in chunk.thinking:
                if isinstance(thinking_part, TextChunk):
                    thinking_parts.append(thinking_part.text)
        elif isinstance(chunk, TextChunk):
            answer_parts.append(chunk.text)
    return "".join(answer_parts), "".join(thinking_parts)


# ===== One answer =====

def generate_answer(client: Mistral, model: str, reasoning_effort: str, answer_rules: str, question_text: str,
                    retrieved_chunks: list[dict]) -> AnswerReply:
    """Generates the model's answer to one question from the retrieved chunks: the generate step after retrieve."""

    # Ask with the RulesAnswer schema, the same strict schema chat.parse would send
    response = client.chat.complete(
        model=model,
        messages=build_answer_prompt(answer_rules, question_text, retrieved_chunks),
        response_format=response_format_from_pydantic_model(RulesAnswer),
        reasoning_effort=reasoning_effort,
        temperature=0,
        top_p=1,
        max_tokens=MAX_ANSWER_TOKENS,
    )
    choice = response.choices[0]
    raw_reply, thinking = split_reply_content(choice.message.content)
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens

    # Parse here, so a bad reply still reports its tokens; keep the finish reason, so a cut-off reply shows "length"
    try:
        rules_answer = RulesAnswer.model_validate_json(raw_reply)
    except ValidationError as error:
        return AnswerReply(
            answer=None,
            is_format_error=True,
            error_message=f"finish reason {choice.finish_reason}: {error}",
            raw_reply=raw_reply,
            thinking=thinking,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    return AnswerReply(
        answer=rules_answer,
        is_format_error=False,
        error_message=None,
        raw_reply=raw_reply,
        thinking=thinking,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
