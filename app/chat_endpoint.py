"""
POST /chat: takes one rules question and streams the answer back as server-sent events (record 0031).

The stream holds a "progress" event for each ProgressUpdate the bot sends (slice 2 of
docs/specs/ask-a-rules-question.md, record 0028), then one "answer" event with the whole RulesAnswer as JSON.
Slice 6 adds "error" events.

The app answers only through the bot's answer(question, report_progress=...) method (CLAUDE.md, "The app").
Until slice 4 the bot is the stub, so this endpoint costs nothing to call.
"""

import queue
import threading
from collections.abc import Iterable

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from answer_flows.shared.answer_shape import RulesAnswer
from answer_flows.shared.progress_updates import ProgressUpdate
from app.stub_rules_bot import StubRulesBot


# Constants
## Seconds the app's stub holds each step, so each one can be read (Job, 17 Nov, after trying slice 2)
STUB_SECONDS_BETWEEN_UPDATES = 1.5


# ===== The request =====

class ChatRequest(BaseModel):
    """What the page sends: the question, as typed."""

    question: str


# ===== The bot the endpoint answers with =====

# Returns the bot that answers /chat; tests swap it with app.dependency_overrides
def get_rules_bot() -> StubRulesBot:
    return StubRulesBot(seconds_between_updates=STUB_SECONDS_BETWEEN_UPDATES)


# ===== The endpoint =====

router = APIRouter()


# Answers one question: streams a "progress" event for each update as it comes, then the "answer" event.
# A plain def, so FastAPI runs it outside the event loop, where waiting on the queue blocks nothing (FastAPI SSE tutorial)
@router.post("/chat", response_class=EventSourceResponse)
def stream_chat_answer(chat_request: ChatRequest, rules_bot: StubRulesBot = Depends(get_rules_bot)) -> Iterable[ServerSentEvent]:

    # The bot answers in a worker thread and puts each update, then its answer or its error, on one queue.
    # queue.Queue is safe to call from any thread, so the bot's "still writing" thread can report too (record 0028)
    updates_then_result: queue.Queue[ProgressUpdate | RulesAnswer | Exception] = queue.Queue()

    def answer_in_worker_thread() -> None:
        """Runs the bot and puts its answer, or the exception it raised, on the queue after its updates."""
        try:
            updates_then_result.put(rules_bot.answer(chat_request.question, report_progress=updates_then_result.put))
        except Exception as error:
            updates_then_result.put(error)

    threading.Thread(target=answer_in_worker_thread, daemon=True).start()

    # Stream each update as it comes, and stop after the answer. A while loop, because the number of updates is
    # known only when the answer arrives. The bot's error is raised again here, not swallowed (slice 6 shows it)
    while True:
        item = updates_then_result.get()
        if isinstance(item, ProgressUpdate):
            yield ServerSentEvent(data=item, event="progress")
        elif isinstance(item, Exception):
            raise item
        else:
            yield ServerSentEvent(data=item, event="answer")
            return
