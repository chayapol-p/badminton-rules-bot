"""
POST /chat: takes one rules question and streams the answer back as server-sent events (record 0031).

The stream holds a "progress" event for each ProgressUpdate the bot sends (slice 2 of
docs/specs/ask-a-rules-question.md, record 0028), then one "answer" event with the whole RulesAnswer as JSON, each
citation with its PDF link (slice 3). When the bot fails, an "error" event with a plain message takes the answer's
place, and the server log keeps the bot's own error (slice 4, record 0035).

The app answers only through load_rules_bot() and the bot's answer(question, report_progress=...) method (CLAUDE.md,
"The app"). RULES_BOT in .env picks the bot: the stub when unset, which costs nothing, or the real one.
"""

import logging
import queue
import threading
from collections.abc import Iterable

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from answer_flows.rules_bot import RulesBot, load_rules_bot
from answer_flows.shared.answer_shape import RulesAnswer
from answer_flows.shared.progress_updates import ProgressUpdate
from app.pdf_links import add_pdf_links
from app.settings import Settings
from app.stub_rules_bot import StubRulesBot


# Constants
## Seconds the app's stub holds each step, so each one can be read (Job, 17 Nov, after trying slice 2)
STUB_SECONDS_BETWEEN_UPDATES = 1.5

## What the page shows for any failed answer (spec criterion 5); the log keeps the real reason
FAILED_ANSWER_MESSAGE = "Couldn't write a checked answer. Please try again."

logger = logging.getLogger(__name__)


# ===== The request =====

class ChatRequest(BaseModel):
    """What the page sends: the question, as typed."""

    question: str


# ===== The bot the endpoint answers with =====

# Returns the bot RULES_BOT names: the real bot, loaded with its clauses and client, or the stub (record 0035)
def choose_rules_bot(settings: Settings) -> RulesBot | StubRulesBot:
    if settings.rules_bot == "real":
        return load_rules_bot()
    return StubRulesBot(seconds_between_updates=STUB_SECONDS_BETWEEN_UPDATES)


# Returns the bot the app loaded at startup (app/main.py); tests swap it with app.dependency_overrides
def get_rules_bot(request: Request) -> RulesBot | StubRulesBot:
    return request.app.state.rules_bot


# ===== The endpoint =====

router = APIRouter()


# Answers one question: streams a "progress" event for each update as it comes, then the "answer" event, or an
# "error" event when the bot fails.
# A plain def, so FastAPI runs it outside the event loop, where waiting on the queue blocks nothing (FastAPI SSE tutorial)
@router.post("/chat", response_class=EventSourceResponse)
def stream_chat_answer(chat_request: ChatRequest,
                       rules_bot: RulesBot | StubRulesBot = Depends(get_rules_bot)) -> Iterable[ServerSentEvent]:

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

    # Stream each update as it comes, and stop after the answer or the error. A while loop, because the number of
    # updates is known only when the answer arrives
    while True:
        item = updates_then_result.get()
        if isinstance(item, ProgressUpdate):
            yield ServerSentEvent(data=item, event="progress")
        elif isinstance(item, Exception):
            # The log keeps the bot's own error, which names the call that failed; the page gets the plain message
            logger.error("The bot failed to answer %r", chat_request.question, exc_info=item)
            yield ServerSentEvent(data={"message": FAILED_ANSWER_MESSAGE}, event="error")
            return
        else:
            # Each citation gets the link that opens its PDF at the clause's page (slice 3, record 0034)
            yield ServerSentEvent(data=add_pdf_links(item), event="answer")
            return
