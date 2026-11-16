"""
What the model writes in one call (setup A, and slice 4 with tools): its reasoning, each part with the sentences
that answer it and that part's answer, then any related sentences. Code builds RulesAnswer from it
(experiments/retired_flows/single_call/assemble_answer.py).
"""

from pydantic import BaseModel, Field

from answer_flows.shared.answer_shape import SentenceCitation


# ===== What the model writes =====

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
