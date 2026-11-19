"""
The topic check in front of the flow: a question that has nothing to do with badminton gets one short, polite reply,
with no search and no model call (docs/specs/refuse-off-topic-questions-fast.md; badminton-wide, Job, 18 Nov).

A check is a function that takes the question and returns True for a rules question. The real check is one
Mistral Small call (mistral_draft_model) with a strict yes/no reply, a 5 s limit and no retries; the stub check calls
only "test" off topic and serves the app's stub bot, so tests stay free. A check that fails or replies in another shape
raises, and RulesBot then lets the question through (criterion 5).

Use:
    is_rules_question = build_mistral_topic_check(mistral_client, settings.mistral_draft_model)
    if not is_rules_question(question_text):
        return build_off_topic_answer()
"""

from collections.abc import Callable

from mistralai.client import Mistral
from mistralai.client.utils import BackoffStrategy, RetryConfig
from mistralai.extra import response_format_from_pydantic_model
from pydantic import BaseModel, Field

from answer_flows.shared.answer_shape import RulesAnswer


# Constants
## The reply every off-topic question gets (Job, 19 Nov: ask only about badminton, or be more specific)
OFF_TOPIC_REPLY = ("I can only help with questions about badminton, from the official BWF rule books. If your "
                   "question is about badminton, can you be more specific? For example: \"I'm bleeding, can I stop "
                   "playing?\"")

## The questions the stub check calls off topic, as typed after trimming and lower-casing
STUB_OFF_TOPIC_QUESTIONS = {"test"}

## What every check takes and returns: the question, and True for a rules question
IsRulesQuestion = Callable[[str], bool]

## The real check's limit: 5 s, and no retries, because a retry would blow the 5 s target (Job, 17 Nov)
CHECK_TIMEOUT_MS = 5_000
NO_RETRIES = RetryConfig("none", BackoffStrategy(0, 0, 1.0, 0), retry_connection_errors=False)

## The real check's instructions. Badminton-wide (Job, 18 Nov): only a question with nothing to do with badminton is
## off topic; any badminton question goes on to the flow, which answers it or says the rules don't cover it.
## The court and equipment line (Job, 18 Nov) keeps a question that never names the sport, such as the net cord's
## tension in newtons, from reading as physics.
## The scoring line (Job, 18 Nov) does the same for short play questions, such as "How long is the break at 11?".
## A framing sentence in their place was tried and reverted (Job, 18 Nov): it blocked the break question again.
## "When unsure, answer true" sends a doubt to the full flow, so a rules question is never refused by mistake
TOPIC_CHECK_PROMPT = (
    "You check whether a question is about badminton, before a rules bot searches the official BWF rule books (the "
    "Laws of Badminton, the Instructions to Technical Officials and the Alternative Laws). Answer true for any "
    "question about badminton: its rules, play, scoring, equipment, officials, players, tournaments, coaching, "
    "technique, training, history or anything else to do with the sport. It is still a badminton question when it "
    "is casual, very short, misspelled, or compares badminton with another sport. Questions about courts, nets, posts, "
    "shuttles, rackets, line judges, umpires or other match officials are about badminton even when they do not name "
    "the sport. Short questions about play, scoring, points, games, intervals, breaks, service or faults are about "
    "badminton even when they do not name the sport. Answer false only when the question is not about badminton at "
    "all: greetings and tests, other subjects, or another sport on its own. When unsure, answer true."
)


# ===== The real check's reply =====

class TopicVerdict(BaseModel):
    """The real check's whole reply: one strict true or false."""

    is_badminton_question: bool = Field(description="True when the question is about badminton")


# ===== The checks =====

def pass_every_question(question_text: str) -> bool:
    """Calls every question a rules question: the check for callers with none, such as the eval runs."""
    return True


def is_rules_question_by_stub(question_text: str) -> bool:
    """Calls only "test" off topic, in any case and with spaces around it (the app's stub bot uses it)."""
    return question_text.strip().lower() not in STUB_OFF_TOPIC_QUESTIONS


def build_mistral_topic_check(mistral_client: Mistral, model: str) -> IsRulesQuestion:
    """Returns the real check: one call on the given model per question. A timeout, an error or a reply outside the
    TopicVerdict shape raises, so the caller decides what a failed check means."""

    def is_rules_question_by_model(question_text: str) -> bool:
        """Asks the model whether the question is about badminton, and returns its true or false."""
        response = mistral_client.chat.complete(
            model=model,
            messages=[{"role": "system", "content": TOPIC_CHECK_PROMPT}, {"role": "user", "content": question_text}],
            response_format=response_format_from_pydantic_model(TopicVerdict),
            temperature=0,
            timeout_ms=CHECK_TIMEOUT_MS,
            retries=NO_RETRIES,
        )
        # strict=True: "maybe" or "yes" in place of a true or false is a broken reply, not a guess to repair
        verdict = TopicVerdict.model_validate_json(response.choices[0].message.content, strict=True)
        return verdict.is_badminton_question

    return is_rules_question_by_model


# ===== The reply =====

def build_off_topic_answer() -> RulesAnswer:
    """Returns the fixed off-topic refusal: no citations, no related rules."""
    return RulesAnswer(reasoning="The topic check found the question is not about badminton.",
                       refused=True, refusal_kind="off_topic", answer=OFF_TOPIC_REPLY, citations=[],
                       related_citations=[])
