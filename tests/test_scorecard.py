"""Tests the scorecard (record 0027): each line per answer, the gate, and the run's shares and combined metric."""

from evals.scorecard import GATE_LINES, METRIC_WEIGHTS, SCORECARD_LINES, build_scorecard, summarise_scorecards


# ===== Sample answer lines and grades =====

def answer_line(refusal_outcome: str = "answered", citation_problems: list[dict] = (),
                code_failures: list[str] = (), is_format_error: bool = False) -> dict:
    """Returns the fields of one answer line the scorecard reads."""
    return {"is_format_error": is_format_error, "refusal_outcome": refusal_outcome,
            "citation_problems": list(citation_problems), "code_failures": list(code_failures)}


def grade(key_facts: bool = True, only_from_sources: bool = True, follows_pass_rule: bool = True,
          readable: bool = True) -> dict:
    """Returns a judge grade as the grade line saves it."""
    verdicts = {"key_facts": key_facts, "only_from_sources": only_from_sources,
                "follows_pass_rule": follows_pass_rule, "readable": readable}
    return {line_name: {"passed": passed, "reason": "sample reason"} for line_name, passed in verdicts.items()}


# ===== One answer =====

def test_a_clean_answer_passes_every_line_and_the_gate():
    scorecard = build_scorecard(answer_line(), grade())
    assert all(scorecard[line_name] for line_name in SCORECARD_LINES)
    assert scorecard["passed"]


def test_readable_failing_alone_keeps_the_gate_passed():
    scorecard = build_scorecard(answer_line(), grade(readable=False))
    assert not scorecard["readable"]
    assert scorecard["passed"]


def test_each_code_check_is_its_own_line():
    citation_problem = {"chunk_id": None, "problem": "sentence 2 has no marker"}
    scorecard = build_scorecard(answer_line(refusal_outcome="false refusal", citation_problems=[citation_problem],
                                            code_failures=["wrong clause: cites none of the clauses that hold the answer"]),
                                grade())
    assert (scorecard["refusal_right"], scorecard["citations_valid"], scorecard["right_clause"]) == (False, False, False)
    assert scorecard["correct"], "a code failure leaves the judge's lines as the judge graded them"
    assert not scorecard["passed"]


def test_a_format_error_fails_every_line():
    scorecard = build_scorecard(answer_line(refusal_outcome=None, is_format_error=True), None)
    assert not any(scorecard.values())


def test_the_gate_and_the_weights_match_record_0027():
    assert set(GATE_LINES) == {"correct", "grounded", "behaviour", "citations_valid", "refusal_right", "right_clause"}
    assert METRIC_WEIGHTS == {"correct": 30, "grounded": 35, "behaviour": 10, "refusal_right": 10, "readable": 15}
    assert sum(METRIC_WEIGHTS.values()) == 100


# ===== One run =====

def test_the_run_reports_each_lines_share_and_the_weighted_metric():
    grade_lines = [
        {"scorecard": build_scorecard(answer_line(), grade())},
        {"scorecard": build_scorecard(answer_line(), grade(only_from_sources=False, readable=False))},
        {"scorecard": build_scorecard(answer_line(refusal_outcome="missed refusal"), grade(key_facts=False))},
        {"scorecard": build_scorecard(answer_line(refusal_outcome=None, is_format_error=True), None)},
    ]
    run_scorecard = summarise_scorecards(grade_lines)
    assert run_scorecard["line_shares"]["correct"] == 0.5
    assert run_scorecard["line_shares"]["grounded"] == 0.5
    assert run_scorecard["line_shares"]["readable"] == 0.5
    assert run_scorecard["gate_passed"] == 1
    # correct 2/4, grounded 2/4, behaviour 3/4, refusal right 2/4, readable 2/4
    assert run_scorecard["combined_metric"] == round(30 * 0.5 + 35 * 0.5 + 10 * 0.75 + 10 * 0.5 + 15 * 0.5, 2)
