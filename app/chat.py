"""
The /chat endpoint: one badminton rules question in, one cited answer out.

Slice 1 serves a stub answer (app/stub/answer.py) in the exact wire shape the chat
UI will consume: answer text with inline [n] markers plus the numbered source list.
The route calls one function, so the real answer flow swaps in at that single call
site later, without touching the route or the contract.
"""

from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, Field, StringConstraints

router = APIRouter()


class ChatRequest(BaseModel):
    """What the chat UI sends: one question."""

    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="The rules question, such as 'How high can I serve?'"
    )


class SourceEntry(BaseModel):
    """One numbered source in the answer's source list."""

    cite_no: int = Field(description="The [n] marker in the answer text that points to this source, counted from 1")
    chunk_id: str = Field(description="The id of the rule chunk, such as laws-9.1.4")
    quote: str = Field(description="The exact words from the source that support the claim, copied unchanged")
    source_name: str = Field(description="The document, version and clause, such as 'Laws of Badminton 5.0 (2), Clause 9.1.4'")


class ChatReply(BaseModel):
    """What /chat returns: the answer text and its numbered source list."""

    answer: str = Field(description="The answer, with the source numbers in square brackets right after each claim, such as [1] or [2][3]")
    sources: list[SourceEntry] = Field(description="The numbered source list; cite_no runs from 1 to len(sources)")


# The one endpoint. The answerer is the single swap point: the stub today, the real flow later
@router.post("/chat", response_model=ChatReply)
def post_chat(request: ChatRequest) -> ChatReply:
    from app.stub.answer import stub_answer

    return stub_answer(request.question)
