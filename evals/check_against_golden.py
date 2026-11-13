"""
Checks an answer against its golden question: did it cite a clause that holds the answer, and does it carry the golden answer's numbers?

These need the golden set, so they run in the eval, not on live requests.
  - cites_expected_clause: a fail when it's False. An answer that cites none of the clauses
    holding the answer rests on the wrong sources, however good it reads.
  - find_missing_golden_numbers: a warning only, for the judge to weigh. A golden answer can
    carry context numbers that aren't required ("the standard Laws put it at 11"), so a missing
    number is not a fail by itself.
"""

from evals.checks.check_numbers import numbers_in
from evals.golden_answer_chunks import expected_chunk_ids


# ===== Did the answer cite a clause that holds the answer? =====

def cites_expected_clause(cited_ids: set[str], question: dict, chunks: list[dict]) -> bool:
    """True when the citations include at least one chunk at one of the question's answer locations."""
    expected_ids = set()
    for location in question["answer_locations"]:
        expected_ids.update(expected_chunk_ids(location, chunks))
    return not cited_ids.isdisjoint(expected_ids)


# ===== Does it carry the golden answer's numbers? =====

def find_missing_golden_numbers(answer_text: str, golden_answer: str) -> list[str]:
    """Returns the numbers in the golden answer that the answer doesn't carry, sorted."""
    return sorted(numbers_in(golden_answer).difference(numbers_in(answer_text)))
