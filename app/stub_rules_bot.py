"""
The stub rules bot: a stand-in for RulesBot that returns one fixed, correctly shaped answer and never calls Mistral.

Before its answer it sends four progress updates, a moment apart (slice 2): the app waits 1.5 s between them, tests
0 s. The app answers with it until slice 4 of docs/specs/ask-a-rules-question.md connects the real bot, and the app
tests keep using it after that, so no test calls a paid API (CLAUDE.md, "The app").

Its answer, SAMPLE_POSTS_ANSWER, is a real sample: the quote is the text of Laws of Badminton clause 1.4 as printed
(tests/test_chat_endpoint.py checks it). The front-end tests read the same file.

It refuses exactly one question, STUB_REFUSED_QUESTION, with SAMPLE_REFUSAL_ANSWER: the real bot's refusal of that
question in the 17 Nov run (slice 5; tests/test_chat_refusals.py checks the copy). It answers "test" with the
off-topic reply, as the real bot's topic check does (slice 7).

Use:
    rules_bot = StubRulesBot()
    rules_answer = rules_bot.answer("How tall are the posts?")
"""

import time
from pathlib import Path

from answer_flows.shared.answer_shape import RulesAnswer
from answer_flows.topic_screen import build_off_topic_answer, is_rules_question_by_stub
from answer_flows.shared.progress_updates import (
    describe_still_writing,
    describe_writing,
    FINDING_RULES,
    FOUND_RULES,
    ignore_progress,
    ProgressUpdate,
    ReportProgress,
)


# Constants
## The sample answer the stub returns, shared with the front-end tests
SAMPLE_POSTS_ANSWER_FILE = Path(__file__).resolve().parent / "sample_posts_answer.json"
SAMPLE_POSTS_ANSWER = RulesAnswer.model_validate_json(SAMPLE_POSTS_ANSWER_FILE.read_text())

## The one question the stub refuses, and the real refusal it answers with
STUB_REFUSED_QUESTION = "What force, in newtons, should the net cord be stretched to?"
SAMPLE_REFUSAL_ANSWER_FILE = Path(__file__).resolve().parent / "sample_refusal_answer.json"
SAMPLE_REFUSAL_ANSWER = RulesAnswer.model_validate_json(SAMPLE_REFUSAL_ANSWER_FILE.read_text())

## The progress updates the stub sends before its answer, shaped like the real flow's (slice 2)
STUB_PROGRESS_UPDATES = [
    ProgressUpdate(step=FINDING_RULES, message="Searching the rule books"),
    ProgressUpdate(step=FOUND_RULES, message="Found 5 rules to check"),
    describe_writing(),
    describe_still_writing(5),
]


# ===== The stub bot =====

class StubRulesBot:
    """Answers every question with the sample answer about the posts; takes the same arguments as RulesBot.answer."""

    def __init__(self, seconds_between_updates: float = 0):
        """Keeps how long to wait after each update: the app waits so each step can be read, tests don't wait."""
        self.seconds_between_updates = seconds_between_updates

    def answer(self, question_text: str, report_progress: ReportProgress = ignore_progress) -> RulesAnswer:
        """Sends the stub's progress updates a moment apart, then returns the refusal for its one refused question,
        or the posts answer for any other."""
        for update in STUB_PROGRESS_UPDATES:
            report_progress(update)
            time.sleep(self.seconds_between_updates)
        if not is_rules_question_by_stub(question_text):
            return build_off_topic_answer()
        if question_text == STUB_REFUSED_QUESTION:
            return SAMPLE_REFUSAL_ANSWER
        return SAMPLE_POSTS_ANSWER
