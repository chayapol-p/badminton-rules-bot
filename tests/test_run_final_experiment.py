"""
Tests for the final experiment's question set and its code-only scoring (experiments/run_final_experiment.py).
No test calls an API.
"""

from evals.checks.check_refusals import should_refuse
from evals.golden_answer_chunks import expected_chunk_ids
from experiments.run_final_experiment import load_locked_questions, pick_one_per_category, score_run
from retrieval.load_rule_chunks import load_chunks
from tests.rule_data import skip_without_rule_data


# ===== The locked question set =====

def test_question_set_has_10_off_topic_10_not_covered_and_20_linked():
    questions, _ = load_locked_questions()
    categories = [question["category"] for question in questions]
    assert categories.count("refusal_probe") == 10
    assert categories.count("unanswerable") == 10
    assert categories.count("cross_reference") == 20


def test_only_the_linked_questions_should_be_answered():
    questions, _ = load_locked_questions()
    for question in questions:
        is_linked = question["category"] == "cross_reference"
        assert should_refuse(question) is not is_linked, question["id"]


def test_every_answer_location_names_a_real_clause():
    skip_without_rule_data()
    questions, _ = load_locked_questions()
    chunks = load_chunks()
    for question in questions:
        for location in question.get("answer_locations", []):
            assert expected_chunk_ids(location, chunks), f"{question['id']}: {location}"


def test_question_ids_are_unique():
    questions, _ = load_locked_questions()
    ids = [question["id"] for question in questions]
    assert len(ids) == len(set(ids))


# ===== The dry run =====

def test_dry_run_picks_the_first_question_of_each_category():
    questions = [{"id": "a", "category": "x"}, {"id": "b", "category": "y"}, {"id": "c", "category": "x"}]
    assert [question["id"] for question in pick_one_per_category(questions)] == ["a", "b"]


# ===== Scoring =====

def make_answer_line(question_id: str, should_refuse_it: bool, outcome: str, code_failures: list[str],
                     tool_rounds: int, cost: float) -> dict:
    """Returns a minimal answer line with what score_run reads."""
    return {"id": question_id, "should_refuse": should_refuse_it, "refusal_outcome": outcome,
            "code_failures": code_failures, "citation_problems": [], "is_format_error": False,
            "error_message": None, "tool_rounds": tool_rounds, "model_calls": 2, "answer_cost": cost,
            "answer_seconds": 10.0}


def test_score_run_counts_refusals_clauses_and_tool_turns():
    answer_lines = [
        make_answer_line("off-topic", True, "correct refusal", [], 0, 0.0),
        make_answer_line("not-covered", True, "missed refusal", ["missed refusal"], 2, 0.02),
        make_answer_line("linked-good", False, "answered", [], 1, 0.01),
        make_answer_line("linked-wrong-clause", False, "answered",
                         ["wrong clause: cites none of the clauses that hold the answer"], 3, 0.03),
        make_answer_line("linked-refused", False, "false refusal", ["false refusal"], 0, 0.01),
    ]
    scores = score_run(answer_lines)
    assert scores["should_refuse"] == 2
    assert scores["correct_refusals"] == 1
    assert scores["missed_refusals"] == ["not-covered"]
    assert scores["false_refusals"] == ["linked-refused"]
    assert scores["answered_linked"] == 2
    assert scores["cites_right_clause"] == 1
    assert scores["mean_tool_rounds_linked"] == round((1 + 3 + 0) / 3, 3)
    assert scores["total_cost"] == 0.07
