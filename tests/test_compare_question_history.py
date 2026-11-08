"""
Tests the question-by-question comparison of runs: regressions and gains.
"""

from experiments.compare_question_history import compare_runs


# ===== Tests =====

def test_a_question_that_always_passed_and_now_fails_is_a_regression():
    baseline_runs = [{"post-height": True, "red-card": False}, {"post-height": True, "red-card": True}]
    candidate_runs = [{"post-height": False, "red-card": True}]
    assert compare_runs(baseline_runs, candidate_runs)["regressions"] == ["post-height"]


def test_a_question_that_never_passed_and_now_always_passes_is_a_gain():
    baseline_runs = [{"leaving-court": False}, {"leaving-court": False}]
    candidate_runs = [{"leaving-court": True}, {"leaving-court": True}]
    comparison = compare_runs(baseline_runs, candidate_runs)
    assert comparison["gains"] == ["leaving-court"]
    assert comparison["regressions"] == []


def test_a_question_that_moved_before_is_neither():
    baseline_runs = [{"red-card": True}, {"red-card": False}]
    candidate_runs = [{"red-card": False}]
    assert compare_runs(baseline_runs, candidate_runs) == {"regressions": [], "gains": []}
