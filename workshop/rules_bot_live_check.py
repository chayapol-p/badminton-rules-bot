"""Asks the product entry point one question with no saved vector, and prints each progress update with the second
it arrived, then the answer and its sources. Run: PYTHONPATH=. uv run python workshop/rules_bot_live_check.py"""

import time

from answer_flows.rules_bot import load_rules_bot
from answer_flows.shared.progress_updates import ProgressUpdate


# Constants
## A question with no saved vector, as an app user would ask it
QUESTION = "Can I serve while my partner is still walking to the court?"


# Print each update with the seconds since the question was asked
started = time.perf_counter()


def print_update(update: ProgressUpdate) -> None:
    """Prints one progress update, with any quoted sources under it."""
    print(f"{time.perf_counter() - started:5.1f} s  {update.message}", flush=True)
    for source in update.sources:
        print(f"         {source.source_name}: {source.quote[:80]}", flush=True)


# Ask the question, then print the answer sentences and the numbered sources
rules_answer = load_rules_bot().answer(QUESTION, report_progress=print_update)
print(f"{time.perf_counter() - started:5.1f} s  answer ready, refused: {rules_answer.refused}")
for sentence in rules_answer.answer_sentences:
    print(" ", sentence.text)
for number, citation in enumerate(rules_answer.citations, start=1):
    print(f"[{number}] {citation.source_name}")
