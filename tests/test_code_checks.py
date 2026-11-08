"""
Tests every code check on one answer: what fails, what only warns, and what is checked only for answered questions.
"""

from evals.code_checks import find_code_failures
from tests.sample_data import SAMPLE_CHUNKS, SAMPLE_QUESTIONS


# ===== A sample answer line, in the run's shape =====

CHUNK_BY_ID = {chunk["id"]: chunk for chunk in SAMPLE_CHUNKS}
POSTS_QUESTION = SAMPLE_QUESTIONS[1]
CEILING_QUESTION = SAMPLE_QUESTIONS[2]


def answer_line(answer_text: str, cited_id: str, refusal_outcome: str, citation_problems: list[dict]) -> dict:
    """Returns one answer line to the posts question, shown Laws 1.4 and 7.4, citing one clause."""
    return {
        "id": "post-height",
        "question": POSTS_QUESTION["question"],
        "retrieved_ids": ["laws-1.4", "laws-7.4"],
        "is_format_error": False,
        "answer": {
            "reasoning": "Law 1.4 gives the height.",
            "refused": refusal_outcome in {"false refusal", "correct refusal"},
            "answer": answer_text,
            "citations": [{"chunk_id": cited_id, "quote": "sample quote"}],
        },
        "citation_problems": citation_problems,
        "refusal_outcome": refusal_outcome,
    }


# ===== Tests =====

def test_a_clean_answer_has_no_failures_and_no_warnings():
    line = answer_line("1.55 metres, and they stay vertical.", "laws-1.4", "answered", [])
    assert find_code_failures(line, POSTS_QUESTION, SAMPLE_CHUNKS, CHUNK_BY_ID) == ([], [])


def test_a_format_error_stops_every_other_check():
    line = dict(answer_line("", "laws-1.4", "answered", []), is_format_error=True, answer=None)
    assert find_code_failures(line, POSTS_QUESTION, SAMPLE_CHUNKS, CHUNK_BY_ID) == (["format error"], [])


def test_refusal_citation_number_and_clause_failures_are_all_listed():
    quote_problem = [{"chunk_id": "laws-7.4", "problem": "quote not in clause", "quote": "x", "clause_text": "y"}]
    line = answer_line("1.55 metres since 1992.", "laws-7.4", "answered", quote_problem)
    failures, _ = find_code_failures(line, POSTS_QUESTION, SAMPLE_CHUNKS, CHUNK_BY_ID)
    assert failures == [
        "citation [laws-7.4] quote not in clause",
        "numbers from nowhere: 1992",
        "wrong clause: cites none of the clauses that hold the answer",
    ]


def test_a_missing_golden_number_only_warns():
    line = answer_line("They stand vertical when the net is strained.", "laws-1.4", "answered", [])
    failures, warnings = find_code_failures(line, POSTS_QUESTION, SAMPLE_CHUNKS, CHUNK_BY_ID)
    assert failures == []
    assert warnings == ["golden answer numbers not in the reply: 1.55"]


def test_a_number_in_the_question_counts_as_shown():
    deuce_question = SAMPLE_QUESTIONS[0]
    line = dict(answer_line("At 20-20, a two-point lead wins; at 29-all, the 30th point.", "laws-7.4", "answered", []),
                question=deuce_question["question"])
    line["retrieved_ids"] = ["laws-7.4", "laws-7.5"]
    failures, _ = find_code_failures(line, deuce_question, SAMPLE_CHUNKS, CHUNK_BY_ID)
    assert failures == []


def test_a_wrong_refusal_fails_and_skips_the_golden_checks():
    line = answer_line("I can't answer that from the rules.", "laws-1.4", "false refusal", [])
    assert find_code_failures(line, POSTS_QUESTION, SAMPLE_CHUNKS, CHUNK_BY_ID) == (["false refusal"], [])


def test_a_correct_refusal_gets_no_golden_checks():
    line = answer_line("The rules give no ceiling height.", "laws-1.4", "correct refusal", [])
    assert find_code_failures(line, CEILING_QUESTION, SAMPLE_CHUNKS, CHUNK_BY_ID) == ([], [])
