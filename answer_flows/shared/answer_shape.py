"""
The checked answer every flow returns, and the sentence citation every flow's model writes.

Each flow's own model shapes live in its folder: answer_flows/gather_then_write/answer_shape.py (slice 5, the product
flow) and, for the retired flows, experiments/retired_flows/single_call/answer_shape.py (ModelAnswer, setup A and slice 4).

SentenceCitation  what every flow's model writes for one sentence: a chunk id and a sentence number.
AnswerSentence    one sentence of a natural answer, with inline [n] markers, or a gap with none (record 0027).
Citation          one claim's source in the checked answer: a chunk id, the quote code copied in and the
                  source's name (document, version, clause), which the answer text itself leaves out.
RulesAnswer       what every check, the judge and the run files read, built by code: the answer text,
                  each citation with its sentence copied in as the quote, and the refusal, which code sets
                  when no part has a sentence that answers it.

Mistral's chat.complete takes each flow's model shape as the response_format (Mistral's structured-output docs).
The field descriptions go into the JSON schema the model sees, so they double as instructions.

Field order matters: the model writes the fields in schema order, so reasoning comes first and
the parts are picked after it. A model only reasons in words it writes
(Anthropic's "Let Claude think" guide), and a reasoning field placed before the answer is a
common structured-output pattern. One public experiment found field order made little
difference, so treat it as something to measure, not a given.
"""

from typing import Literal

from pydantic import BaseModel, Field


# ===== One citation =====

class Citation(BaseModel):
    """One claim's source: the id of a chunk the model was shown, and the exact words it relies on."""

    chunk_id: str = Field(description="The id in square brackets at the top of the source, such as laws-7.4")
    quote: str = Field(description="The exact words from that source that support the claim, copied unchanged")
    # Empty by default, so run files from before still load
    source_name: str = Field(default="", description="The document, version and clause, such as 'Laws of Badminton 5.0 (2), Clause 1.4'")


# ===== One sentence of a natural answer =====

class AnswerSentence(BaseModel):
    """One sentence of the answer: its text with inline [n] markers, or a gap that says what the rules don't cover."""

    # The flag comes first, so the model decides whether a sentence is a gap before writing it
    is_gap: bool = Field(description="True only for a sentence that says what the rules don't cover, such as a part marked NO SOURCE; a gap sentence carries no marker")
    text: str = Field(description="One sentence, with the numbers of the sentences it rests on in square brackets right after each claim, such as [1] or [2][3]; no number in a gap sentence")


# ===== The whole answer =====

class RulesAnswer(BaseModel):
    """The bot's answer to one question."""

    reasoning: str = Field(description="Before deciding: which sources bear on the question, and whether together they answer what was asked. Name what is missing, if anything.")
    refused: bool = Field(description="True when the sources don't answer the question that was asked")
    # Which kind of refusal, set by code: "off_topic" from the topic check, "not_covered" from the flow, so the app
    # labels only the second. Empty for answers, and for run files from before (Job, 17 Nov)
    refusal_kind: Literal["off_topic", "not_covered"] | None = None
    answer: str = Field(description="The answer. When refusing, say what the sources do cover and what they don't.")
    citations: list[Citation] = Field(description="One citation per claim; empty only when no source applies")
    # Related sentences are context, never the answer, so they get their own list: with one list the judge read
    # them as the answer's sources and failed correct refusals (14 Nov baseline, record 0025). Empty by default,
    # so run files from before still load
    related_citations: list[Citation] = Field(default_factory=list, description="Sentences that bear on the question without answering it; context only")
    # A natural answer (record 0027) keeps its sentences, so the marker check can re-run from a run file: marker [n]
    # points to citations[n - 1]. Empty for refusals, the retired flows and run files from before
    answer_sentences: list[AnswerSentence] = Field(default_factory=list, description="The answer sentence by sentence, when the model wrote it with inline markers")


# ===== One sentence the model cites =====

class SentenceCitation(BaseModel):
    """One sentence the model relies on: a chunk it was shown, and the sentence's number in that chunk."""

    chunk_id: str = Field(description="The id in square brackets at the top of the source, such as laws-7.4")
    sentence: int = Field(description="The number in brackets before the sentence, such as 2 for (2)")
