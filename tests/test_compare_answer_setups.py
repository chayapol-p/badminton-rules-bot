"""
Tests the answer run's scores and the cost of one call, on answer lines written by hand.
"""

from evals.token_costs import call_cost
from experiments.compare_answer_setups import summarise_answer_run


# ===== Sample answer lines =====

## The two outcomes where the bot refused
REFUSED_OUTCOMES = {"correct refusal", "false refusal"}


def answer_line(question_id: str, split: str, category: str, should_refuse: bool, refusal_outcome: str | None,
                citation_problems: list[dict], code_failures: list[str]) -> dict:
    """Returns one answer line in the run's shape; a None outcome means the reply didn't fit the shape."""
    answer = None
    if refusal_outcome is not None:
        answer = {"answer": "sample", "citations": [], "refused": refusal_outcome in REFUSED_OUTCOMES}
    return {
        "id": question_id,
        "split": split,
        "category": category,
        "should_refuse": should_refuse,
        "words_returned": 100,
        "answer": answer,
        "is_format_error": answer is None,
        "citation_problems": citation_problems,
        "refusal_outcome": refusal_outcome,
        "code_failures": code_failures,
        "answer_cost": 0.003,
        "judge_cost": 0.009,
    }


ANSWER_LINES = [
    answer_line("post-height", "dev", "direct_lookup", False, "answered", [], []),
    answer_line("deuce-end", "dev", "direct_lookup", False, "false refusal", [], ["false refusal"]),
    answer_line("red-card", "dev", "cross_reference", False, None, [], ["format error"]),
    answer_line("doubles-court-size", "dev", "diagram", False, "answered", [{"chunk_id": "x", "problem": "not retrieved"}],
                ["citation [x] not retrieved", "numbers from nowhere: 13.4"]),
    answer_line("service-judge-height-signal", "dev", "diagram", False, "false refusal", [], ["false refusal"]),
    answer_line("ceiling-height", "dev", "unanswerable", True, "correct refusal", [], []),
    answer_line("spin-serve-ban-date", "dev", "unanswerable", True, "missed refusal", [], ["missed refusal"]),
    answer_line("string-tension", "probe", "refusal_probe", True, "correct refusal", [], []),
]

PASSED_BY_ID = {
    "post-height": True,
    "deuce-end": False,
    "red-card": False,
    "doubles-court-size": False,
    "service-judge-height-signal": False,
    "ceiling-height": True,
    "spin-serve-ban-date": False,
    "string-tension": True,
}


# ===== Tests =====

def test_answers_are_scored_without_the_image_only_questions():
    scores = summarise_answer_run(ANSWER_LINES, PASSED_BY_ID)
    assert scores["answers_passed"] == 1
    assert scores["answers_scored"] == 3
    assert scores["image_only_scored"] == 2
    assert scores["by_category"]["direct_lookup"] == {"passed": 1, "questions": 2}


def test_refusals_are_counted_both_ways_and_probes_apart():
    scores = summarise_answer_run(ANSWER_LINES, PASSED_BY_ID)
    assert scores["refusals_correct"] == 1
    assert scores["refusals_needed"] == 2
    assert scores["probe_refusals_correct"] == 1
    assert scores["probes"] == 1
    assert scores["false_refusals"] == 1, "the image-only false refusal is left out"
    assert scores["no_answer_passed"] == 2


def test_code_failures_are_counted_by_check_and_only_clean_answers_reach_the_judge():
    scores = summarise_answer_run(ANSWER_LINES, PASSED_BY_ID)
    assert scores["code_failed"] == 5
    assert scores["code_failures_by_check"] == {"format error": 1, "wrong refusal": 3, "citation problem": 1,
                                                "number from nowhere": 1, "wrong clause": 0}
    assert scores["judge_calls"] == 3


def test_citations_are_scored_only_on_replies_that_fit_the_shape():
    scores = summarise_answer_run(ANSWER_LINES, PASSED_BY_ID)
    assert scores["format_errors"] == 1
    assert scores["citation_pass_rate"] == round(6 / 7, 3)


def test_cost_adds_the_answer_and_the_judge():
    scores = summarise_answer_run(ANSWER_LINES, PASSED_BY_ID)
    assert scores["cost_per_question"] == 0.012
    assert scores["total_cost"] == round(8 * 0.012, 3)


def test_one_call_costs_its_tokens_at_the_model_price():
    assert call_cost("claude-sonnet-5-5", 1_000_000, 100_000) == 2.00 + 1.00
