"""
Tests the re-score of a saved run: the code checks decide first, the saved judge verdict decides the rest.
"""

from experiments.rescore_answer_run import rescore_answer_lines
from tests.sample_data import SAMPLE_CHUNKS, SAMPLE_QUESTIONS


# ===== A saved answer line, in the shape of run 1, before code_failures existed =====

def saved_answer_line(answer_text: str) -> dict:
    """Returns one saved answer to the posts question, citing Law 1.4."""
    return {
        "id": "post-height",
        "question": SAMPLE_QUESTIONS[1]["question"],
        "retrieved_ids": ["laws-1.4"],
        "is_format_error": False,
        "answer": {"reasoning": "sample", "refused": False, "answer": answer_text,
                   "citations": [{"chunk_id": "laws-1.4", "quote": "sample quote"}]},
        "citation_problems": [],
        "refusal_outcome": "answered",
    }


QUESTION_BY_ID = {"post-height": SAMPLE_QUESTIONS[1]}


# ===== Tests =====

def test_a_clean_answer_keeps_the_saved_judge_verdict():
    answer_lines = [saved_answer_line("1.55 metres.")]
    assert rescore_answer_lines(answer_lines, {"post-height": True}, QUESTION_BY_ID, SAMPLE_CHUNKS) == {"post-height": True}
    assert answer_lines[0]["code_failures"] == []


def test_a_code_failure_fails_the_answer_whatever_the_judge_said():
    answer_lines = [dict(saved_answer_line("1.55 metres."), refusal_outcome="missed refusal")]
    assert rescore_answer_lines(answer_lines, {"post-height": True}, QUESTION_BY_ID, SAMPLE_CHUNKS) == {"post-height": False}
    assert answer_lines[0]["code_failures"] == ["missed refusal"]
