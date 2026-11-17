"""
POST /chat: takes one rules question and streams the answer back as server-sent events (record 0031).

Slice 1 of docs/specs/ask-a-rules-question.md: the stream holds one event, "answer", with the whole RulesAnswer as
JSON. Later slices add "progress" events (slice 2) and "error" events (slice 6).

The app answers only through the bot's answer(question, report_progress=...) method (CLAUDE.md, "The app").
Until slice 4 the bot is the stub, so this endpoint costs nothing to call.
"""

from collections.abc import Iterable

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from app.stub_rules_bot import StubRulesBot


# ===== The request =====

class ChatRequest(BaseModel):
    """What the page sends: the question, as typed."""

    question: str


# ===== The bot the endpoint answers with =====

# Returns the bot that answers /chat; tests swap it with app.dependency_overrides
def get_rules_bot() -> StubRulesBot:
    return StubRulesBot()


# ===== The endpoint =====

router = APIRouter()


# Answers one question and streams the answer as one "answer" event.
# A plain def, so FastAPI runs the bot's long call outside the event loop (FastAPI SSE tutorial)
@router.post("/chat", response_class=EventSourceResponse)
def stream_chat_answer(chat_request: ChatRequest, rules_bot: StubRulesBot = Depends(get_rules_bot)) -> Iterable[ServerSentEvent]:
    rules_answer = rules_bot.answer(chat_request.question)
    yield ServerSentEvent(data=rules_answer, event="answer")
