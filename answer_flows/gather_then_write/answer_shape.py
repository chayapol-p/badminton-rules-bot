"""
The two shapes of gather-then-write: GatheredAnswer from the gather call (the sentences per part, no answer text) and
WrittenAnswer from the write call (one natural answer, sentence by sentence, with inline [n] markers; record 0027).
"""

from pydantic import BaseModel, Field

from answer_flows.shared.answer_shape import AnswerSentence, SentenceCitation


# ===== The gather call =====

class GatheredPart(BaseModel):
    """One thing the question asks, and the sentences that answer it. The gather call writes no answer text."""

    asks: str = Field(description="One thing the question asks, as words that complete 'The sources do not say …', such as 'the highest string tension allowed'")
    sentences: list[SentenceCitation] = Field(description="The sentences that answer this part; empty when no sentence answers it")


class GatheredAnswer(BaseModel):
    """What the gather call sends: its reasoning, every part with the sentences that answer it, and related sentences."""

    reasoning: str = Field(description="First: each part the question asks, and which sentences in the sources answer it, if any.")
    parts: list[GatheredPart] = Field(description="Every part the question asks, in the question's order")
    related_sentences: list[SentenceCitation] = Field(description="Sentences that bear on the question without answering a part, such as the rule nearest to a part the sources don't answer; often empty")


# ===== The write call =====

class WrittenAnswer(BaseModel):
    """What the write call sends: one connected answer to the whole question, sentence by sentence."""

    sentences: list[AnswerSentence] = Field(description="The answer in reading order: what the user should do, or the direct answer, first; then the rest, joined into one reply")
