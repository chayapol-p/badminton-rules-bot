"""
Tests the grading printout and the grades template, on answer lines written by hand.
"""

from evals.print_answers_for_grading import format_answer_for_grading, template_lines
from tests.sample_data import SAMPLE_CHUNKS, SAMPLE_QUESTIONS


# ===== A sample answer line, in the run's shape =====

CHUNK_BY_ID = {chunk["id"]: chunk for chunk in SAMPLE_CHUNKS}

POSTS_ANSWER_LINE = {
    "id": "post-height",
    "category": "direct_lookup",
    "question": "How tall are the posts that hold the net?",
    "retrieved_ids": ["laws-1.4", "laws-7.4"],
    "is_format_error": False,
    "answer": {
        "reasoning": "Law 1.4 gives the height.",
        "refused": False,
        "answer": "1.55 metres.",
        "citations": [{"chunk_id": "laws-1.4", "quote": "The posts shall be 1.55 metres in height"}],
    },
    "citation_problems": [],
    "refusal_outcome": "answered",
}


# ===== Tests =====

def test_the_printout_shows_what_to_grade_against_and_what_the_bot_wrote():
    printout = format_answer_for_grading(POSTS_ANSWER_LINE, SAMPLE_QUESTIONS[1], CHUNK_BY_ID)
    assert "1.55 metres from the surface of the court" in printout
    assert "[laws-7.4] If the score becomes 20-all" in printout
    assert "Bot answer" in printout
    assert "judge" not in printout.lower()


def test_a_question_without_an_answer_shows_why():
    ceiling_line = dict(POSTS_ANSWER_LINE, id="ceiling-height", category="unanswerable")
    printout = format_answer_for_grading(ceiling_line, SAMPLE_QUESTIONS[2], CHUNK_BY_ID)
    assert "No answer: refuse" in printout


def test_the_template_skips_answers_already_graded():
    lines = template_lines("sample-run", ["post-height", "deuce-end"], graded_ids={"deuce-end"})
    assert lines == [{"run": "sample-run", "id": "post-height", "passed": None, "reason": ""}]
