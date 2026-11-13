"""
The two shapes of an answer: the one the model writes, and the checked one code builds from it.

ModelAnswer   what the model sends: its reasoning, then each part the question asks with the sentences
              that answer it (a chunk id and a sentence number each) and that part's answer, then any
              related sentences. Its one decision per part is which sentences answer it.
GatheredAnswer, WrittenAnswer   slice 5's two calls: the gather call picks the sentences per part with the
              tools (no answer text), and the write call, with no tools, writes one answer per answered part
              (answer/assemble_written_answer.py).
RulesAnswer   what every check, the judge and the run files read, built by code (answer/assemble_answer.py):
              the answer text, each citation with its sentence copied in as the quote, and the refusal,
              which code sets when no part has a sentence that answers it.

Mistral's chat.complete takes ModelAnswer as the response_format (Mistral's structured-output docs).
The field descriptions go into the JSON schema the model sees, so they double as instructions.

Field order matters: the model writes the fields in schema order, so reasoning comes first and
the parts are picked after it. A model only reasons in words it writes
(Anthropic's "Let Claude think" guide), and a reasoning field placed before the answer is a
common structured-output pattern. One public experiment found field order made little
difference, so treat it as something to measure, not a given.
"""

from pydantic import BaseModel, Field


# ===== One citation =====

class Citation(BaseModel):
    """One claim's source: the id of a chunk the model was shown, and the exact words it relies on."""

    chunk_id: str = Field(description="The id in square brackets at the top of the source, such as laws-7.4")
    quote: str = Field(description="The exact words from that source that support the claim, copied unchanged")


# ===== The whole answer =====

class RulesAnswer(BaseModel):
    """The bot's answer to one question."""

    reasoning: str = Field(description="Before deciding: which sources bear on the question, and whether together they answer what was asked. Name what is missing, if anything.")
    refused: bool = Field(description="True when the sources don't answer the question that was asked")
    answer: str = Field(description="The answer. When refusing, say what the sources do cover and what they don't.")
    citations: list[Citation] = Field(description="One citation per claim; empty only when no source applies")


# ===== What the model writes =====

class SentenceCitation(BaseModel):
    """One sentence the model relies on: a chunk it was shown, and the sentence's number in that chunk."""

    chunk_id: str = Field(description="The id in square brackets at the top of the source, such as laws-7.4")
    sentence: int = Field(description="The number in brackets before the sentence, such as 2 for (2)")


class QuestionPart(BaseModel):
    """One thing the question asks, and the sentences that answer it."""

    asks: str = Field(description="One thing the question asks, as words that complete 'The sources do not say …', such as 'the highest string tension allowed'")
    sentences: list[SentenceCitation] = Field(description="The sentences that answer this part; empty when no sentence answers it")
    answer: str = Field(description="The answer to this part, from those sentences only; empty when there are none")


class ModelAnswer(BaseModel):
    """The model's answer to one question: one decision per part, which sentences answer it. Code decides the rest."""

    reasoning: str = Field(description="First: each part the question asks, and which sentences in the sources answer it, if any.")
    parts: list[QuestionPart] = Field(description="Every part the question asks, in the question's order")
    related_sentences: list[SentenceCitation] = Field(description="Sentences that bear on the question without answering a part, such as the rule nearest to a part the sources don't answer; often empty")
    related_note: str = Field(description="What the related sentences say, in one or two sentences; empty when there are none")


# ===== Slice 5: the gather call, then the write call =====

class GatheredPart(BaseModel):
    """One thing the question asks, and the sentences that answer it. The gather call writes no answer text."""

    asks: str = Field(description="One thing the question asks, as words that complete 'The sources do not say …', such as 'the highest string tension allowed'")
    sentences: list[SentenceCitation] = Field(description="The sentences that answer this part; empty when no sentence answers it")


class GatheredAnswer(BaseModel):
    """What the gather call sends: its reasoning, every part with the sentences that answer it, and related sentences."""

    reasoning: str = Field(description="First: each part the question asks, and which sentences in the sources answer it, if any.")
    parts: list[GatheredPart] = Field(description="Every part the question asks, in the question's order")
    related_sentences: list[SentenceCitation] = Field(description="Sentences that bear on the question without answering a part, such as the rule nearest to a part the sources don't answer; often empty")


class PartAnswer(BaseModel):
    """The write call's answer to one part, matched to it by the part's number."""

    part_number: int = Field(description="The number of the part this answers, as given before it: 1 for 'Part 1'")
    answer: str = Field(description="The answer to this part, from its sentences only")


class WrittenAnswer(BaseModel):
    """What the write call sends: one answer for each part that has sentences."""

    answers: list[PartAnswer] = Field(description="One answer for each part that has sentences, in part order; none for a part marked NO SOURCE")
