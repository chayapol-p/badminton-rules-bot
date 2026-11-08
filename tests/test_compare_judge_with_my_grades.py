"""
Tests how your grades are compared with the judge's, with grade lines written by hand.
"""

from evals.compare_judge_with_my_grades import compare_grades


# ===== Sample grade lines, in the shapes the two files use =====

def judge_line(question_id: str, passed: bool) -> dict:
    """Returns a judge grade line with the given verdict; a failed grade fails its key_facts line."""
    return {
        "id": question_id,
        "passed": passed,
        "grade": {
            "key_facts": {"passed": passed, "reason": "sample reason"},
            "only_from_sources": {"passed": True, "reason": "sample reason"},
            "follows_pass_rule": {"passed": True, "reason": "sample reason"},
        },
    }


JUDGE_GRADE_BY_ID = {
    "post-height": judge_line("post-height", True),
    "deuce-end": judge_line("deuce-end", False),
}


# ===== Tests =====

def test_matching_grades_count_and_differing_ones_are_listed():
    my_grades = [
        {"run": "sample-run", "id": "post-height", "passed": True, "reason": "1.55 metres, cited"},
        {"run": "sample-run", "id": "deuce-end", "passed": True, "reason": "Both rules given"},
    ]
    comparison = compare_grades(my_grades, JUDGE_GRADE_BY_ID)
    assert comparison["matched"] == 1
    assert comparison["graded"] == 2
    assert comparison["disagreements"][0]["id"] == "deuce-end"
    assert comparison["disagreements"][0]["judge_reason"] == "key_facts: sample reason"


def test_an_answer_the_code_checks_failed_is_listed_apart_and_not_counted():
    judge_grade_by_id = dict(JUDGE_GRADE_BY_ID, **{"red-card": {"id": "red-card", "passed": False, "judged": False, "grade": None}})
    my_grades = [
        {"run": "sample-run", "id": "post-height", "passed": True, "reason": "1.55 metres, cited"},
        {"run": "sample-run", "id": "red-card", "passed": True, "reason": "Right card, cited"},
    ]
    comparison = compare_grades(my_grades, judge_grade_by_id)
    assert comparison["graded"] == 1
    assert comparison["matched"] == 1
    assert comparison["not_judged_ids"] == ["red-card"]
