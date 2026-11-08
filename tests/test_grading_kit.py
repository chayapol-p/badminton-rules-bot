"""
Tests the grading kit: code-check failures, the sample swap, the printout order and the grades template.
"""

from evals.grading_kit import code_check_failures, format_answer_for_grading, pick_grading_sample, template_lines
from tests.sample_data import SAMPLE_CHUNKS, SAMPLE_QUESTIONS


# ===== Sample answer lines, in the run's shape =====

CHUNK_BY_ID = {chunk["id"]: chunk for chunk in SAMPLE_CHUNKS}


def answer_line(question_id: str, category: str, refusal_outcome: str, citation_problems: list[dict]) -> dict:
    """Returns one answer line in the run's shape, citing Law 1.4."""
    return {
        "id": question_id,
        "category": category,
        "question": "How tall are the posts that hold the net?",
        "retrieved_ids": ["laws-1.4", "laws-7.4"],
        "is_format_error": False,
        "answer": {
            "reasoning": "Law 1.4 gives the height.",
            "refused": False,
            "answer": "1.55 metres.",
            "citations": [{"chunk_id": "laws-1.4", "quote": "The posts shall be 1.55 metres in height"}],
        },
        "citation_problems": citation_problems,
        "refusal_outcome": refusal_outcome,
    }


CLEAN_POSTS_LINE = answer_line("post-height", "direct_lookup", "answered", [])
QUOTE_PROBLEM = [{"chunk_id": "laws-1.4", "problem": "quote not in clause", "quote": "x", "clause_text": "y"}]


# ===== Step 1: code checks =====

def test_a_clean_answer_has_no_code_failures():
    assert code_check_failures(CLEAN_POSTS_LINE) == []


def test_wrong_refusals_and_citation_problems_are_code_failures():
    line = answer_line("deuce-end", "direct_lookup", "false refusal", QUOTE_PROBLEM)
    assert code_check_failures(line) == ["false refusal", "citation [laws-1.4] quote not in clause"]


def test_a_format_error_is_a_code_failure():
    line = dict(CLEAN_POSTS_LINE, is_format_error=True, answer=None)
    assert code_check_failures(line) == ["format error"]


# ===== Step 2: the sample =====

def test_a_failed_answer_is_swapped_for_the_next_clean_one_in_its_category():
    answer_lines = [
        CLEAN_POSTS_LINE,
        answer_line("deuce-end", "direct_lookup", "answered", QUOTE_PROBLEM),
        answer_line("feather-count", "direct_lookup", "answered", []),
    ]
    sample, swap_notes = pick_grading_sample(answer_lines, ["post-height", "deuce-end"])
    assert [line["id"] for line in sample] == ["post-height", "feather-count"]
    assert swap_notes == ["deuce-end failed the code checks; feather-count takes its place"]


# ===== The printout =====

def test_the_printout_puts_code_checks_then_answer_then_question_then_citations():
    printout = format_answer_for_grading(CLEAN_POSTS_LINE, SAMPLE_QUESTIONS[1], CHUNK_BY_ID)
    positions = [printout.index(label) for label in ["Code checks", "Bot answer", "Question", "Expected", "Citations", "clause:"]]
    assert positions == sorted(positions)
    assert "Also shown, not cited: laws-7.4" in printout
    assert "judge" not in printout.lower()


# ===== The grades template =====

def test_the_template_skips_answers_already_in_the_file():
    lines = template_lines("sample-run", ["post-height", "deuce-end"], graded_ids={"deuce-end"})
    assert lines == [{"run": "sample-run", "id": "post-height", "passed": None, "reason": ""}]
