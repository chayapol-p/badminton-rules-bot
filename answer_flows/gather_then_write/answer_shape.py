"""
Slice 5's two shapes: GatheredAnswer from the gather call (the sentences per part, no answer text) and
WrittenAnswer from the write call (one answer per answered part).
"""

from pydantic import BaseModel, Field

from answer_flows.shared.answer_shape import SentenceCitation


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

class PartAnswer(BaseModel):
    """The write call's answer to one part, matched to it by the part's number."""

    part_number: int = Field(description="The number of the part this answers, as given before it: 1 for 'Part 1'")
    answer: str = Field(description="The answer to this part, from its sentences only")


class WrittenAnswer(BaseModel):
    """What the write call sends: one answer for each part that has sentences."""

    answers: list[PartAnswer] = Field(description="One answer for each part that has sentences, in part order; none for a part marked NO SOURCE")
