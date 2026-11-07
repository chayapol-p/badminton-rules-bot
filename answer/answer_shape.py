"""
The fixed shape every answer comes back in, so code can check it instead of reading free text.

Mistral's chat.parse takes RulesAnswer as response_format and hands back a parsed RulesAnswer
(Mistral's structured-output docs). The field descriptions go into the JSON schema the model
sees, so they double as instructions.

Field order matters: the model writes the fields in schema order, so reasoning comes first and
the refuse-or-answer decision is made after it. A model only reasons in words it writes
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
