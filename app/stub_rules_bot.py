"""
The stub rules bot: a stand-in for RulesBot that returns one fixed, correctly shaped answer and never calls Mistral.

The app answers with it until slice 4 of docs/specs/ask-a-rules-question.md connects the real bot, and the app tests
keep using it after that, so no test calls a paid API (CLAUDE.md, "The app").

Its answer, SAMPLE_POSTS_ANSWER, is a real sample: the quote is the text of Laws of Badminton clause 1.4 as printed
(tests/test_chat_endpoint.py checks it). The front-end tests read the same file.

Use:
    rules_bot = StubRulesBot()
    rules_answer = rules_bot.answer("How tall are the posts?")
"""

from pathlib import Path

from answer_flows.shared.answer_shape import RulesAnswer
from answer_flows.shared.progress_updates import ReportProgress, ignore_progress


# Constants
## The sample answer the stub returns, shared with the front-end tests
SAMPLE_POSTS_ANSWER_FILE = Path(__file__).resolve().parent / "sample_posts_answer.json"
SAMPLE_POSTS_ANSWER = RulesAnswer.model_validate_json(SAMPLE_POSTS_ANSWER_FILE.read_text())


# ===== The stub bot =====

class StubRulesBot:
    """Answers every question with the sample answer about the posts; takes the same arguments as RulesBot.answer."""

    def answer(self, question_text: str, report_progress: ReportProgress = ignore_progress) -> RulesAnswer:
        """Returns the sample answer, whatever the question."""
        return SAMPLE_POSTS_ANSWER
