"""
Runs every code check on one saved answer line, and returns the checks it failed and the warnings for the judge.

The order of grading: code decides everything it can decide reliably, and the judge is only
called on answers the code checks passed. Failures:
  - format error: the reply didn't fit the answer shape
  - wrong refusal: a missed refusal or a false refusal
  - citation problem: a cited chunk the model never saw, or a quote not in its clause
  - wrong clause: an answerable question, answered, citing none of the clauses that hold the answer
Warnings, for the judge to weigh:
  - numbers not in the sources: a number in the answer that the sources and the question don't hold.
    It can come from memory (a fail) or be worked out from the sources (an example score like
    22-20), and only the judge can tell which
  - missing golden number: a number in the golden answer the answer doesn't carry, which can be
    context rather than a key fact

Use:
    failures, warnings = find_code_failures(answer_line, question, chunks, chunk_by_id)
"""

from answer.check_numbers import find_ungrounded_numbers
from answer.check_refusals import ANSWERED, FALSE_REFUSAL, MISSED_REFUSAL
from evals.check_against_golden import cites_expected_clause, find_missing_golden_numbers
from retrieval.build_bundle import format_source


# Constants
## Refusal outcomes that already fail
WRONG_REFUSALS = {MISSED_REFUSAL, FALSE_REFUSAL}


# ===== The sources an answer may draw numbers from =====

def build_source_text(answer_line: dict, chunk_by_id: dict[str, dict]) -> str:
    """Returns the source blocks the model was shown, headers included, plus the question it was asked."""
    source_blocks = [format_source(chunk_by_id[chunk_id]) for chunk_id in answer_line["retrieved_ids"]]
    return "\n".join(source_blocks) + "\n" + answer_line["question"]


# ===== Every code check on one answer =====

def find_code_failures(answer_line: dict, question: dict, chunks: list[dict],
                       chunk_by_id: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Returns the code checks one answer failed, and the warnings to pass to the judge."""
    if answer_line["is_format_error"]:
        return ["format error"], []

    failures = []
    warnings = []
    answer = answer_line["answer"]

    # The checks every answer gets: the refusal and the citations fail, the numbers only warn
    if answer_line["refusal_outcome"] in WRONG_REFUSALS:
        failures.append(answer_line["refusal_outcome"])
    for problem in answer_line["citation_problems"]:
        failures.append(f"citation [{problem['chunk_id']}] {problem['problem']}")
    ungrounded_numbers = find_ungrounded_numbers(answer["answer"], build_source_text(answer_line, chunk_by_id))
    if ungrounded_numbers:
        warnings.append(f"numbers not in the sources: {', '.join(ungrounded_numbers)}")

    # The checks only an answered question with a golden answer gets
    if answer_line["refusal_outcome"] == ANSWERED:
        cited_ids = {citation["chunk_id"] for citation in answer["citations"]}
        if not cites_expected_clause(cited_ids, question, chunks):
            failures.append("wrong clause: cites none of the clauses that hold the answer")
        missing_numbers = find_missing_golden_numbers(answer["answer"], question["answer"])
        if missing_numbers:
            warnings.append(f"golden answer numbers not in the reply: {', '.join(missing_numbers)}")
    return failures, warnings
