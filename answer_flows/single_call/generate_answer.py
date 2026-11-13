"""
Asks Mistral for one answer in the ModelAnswer shape, builds the checked answer from it, and returns that with the model's
thinking and the tokens it used.

Fixed for every eval run (experiment rule 2): the pinned model and reasoning effort from
app/settings.py, and temperature 0. Mistral calls temperature 0 greedy sampling and rejects it
unless top_p is exactly 1 (400 error, code 3054), and the SDK sends no top_p of its own, so the
call sets both.

Mistral Large 4 always thinks before it answers, and sends its reply as a list of chunks: thinking
chunks, then text chunks with the answer (Mistral's reasoning docs: there is no plain-text mode).
The answer text is parsed into ModelAnswer and assembled into RulesAnswer (answer_flows/single_call/assemble_answer.py); the thinking
is kept as text for reading failures.

The reply is parsed here, not inside the SDK, so a reply that doesn't fit the shape still reports
the tokens it cost. Such a reply comes back flagged as a format error, with the validation message
and the raw text, and the run records it instead of stopping. Network and API errors still stop
the run; retries come in Stage 4.

Use:
    reply = generate_answer(client, model, reasoning_effort, answer_rules, question_text, source_items)
"""

from dataclasses import dataclass

from mistralai.client import Mistral
from mistralai.extra import response_format_from_pydantic_model
from pydantic import ValidationError

from answer_flows.shared.answer_shape import RulesAnswer
from answer_flows.shared.read_model_reply import MAX_ANSWER_TOKENS, split_reply_content
from answer_flows.single_call.answer_rules import build_answer_prompt
from answer_flows.single_call.answer_shape import ModelAnswer
from answer_flows.single_call.assemble_answer import assemble_answer
from retrieval.build_bundle import format_bundle, full_chunks


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


# ===== One answer =====

def generate_answer(client: Mistral, model: str, reasoning_effort: str, answer_rules: str, question_text: str,
                    source_items: list[dict]) -> AnswerReply:
    """Generates the model's answer to one question from the retrieved chunks: the generate step after retrieve."""

    # Ask with the ModelAnswer schema, the same strict schema chat.parse would send
    response = client.chat.complete(
        model=model,
        messages=build_answer_prompt(answer_rules, question_text, format_bundle(source_items)),
        response_format=response_format_from_pydantic_model(ModelAnswer),
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
        model_answer = ModelAnswer.model_validate_json(raw_reply)
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

    # Code builds the answer from the parts: the quotes from the clauses the model saw in full, and the refusal
    shown_chunk_by_id = {chunk["id"]: chunk for chunk in full_chunks(source_items)}
    return AnswerReply(
        answer=assemble_answer(model_answer, shown_chunk_by_id),
        is_format_error=False,
        error_message=None,
        raw_reply=raw_reply,
        thinking=thinking,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
