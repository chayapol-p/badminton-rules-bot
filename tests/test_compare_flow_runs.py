"""Tests the win call between two flows: ranges apart, ranges touching (consistency decides) and overlap."""

from experiments.compare_flow_runs import FlowRuns, call_winner, measure_consistency


def flow(name: str, metrics: list[float], passed_by_id_per_run: list[dict[str, bool]]) -> FlowRuns:
    """Returns a flow's runs with these metrics and gate verdicts."""
    return FlowRuns(name=name, run_names=[f"run{i}" for i in range(len(metrics))], combined_metrics=metrics,
                    gate_passed_counts=[0] * len(metrics), passed_by_id_per_run=passed_by_id_per_run)


STEADY = [{"q1": True, "q2": False}] * 3
SHAKY = [{"q1": True, "q2": False}, {"q1": True, "q2": True}, {"q1": False, "q2": False}]


def test_consistency_is_the_share_of_questions_with_one_verdict_in_every_run():
    assert measure_consistency(flow("steady", [80, 81, 82], STEADY)) == 1.0
    assert measure_consistency(flow("shaky", [80, 81, 82], SHAKY)) == 0.0


def test_ranges_apart_are_a_win():
    """Record 0026's example: 31, 33, 35 against 36, 37, 38 is a win."""
    assert call_winner(flow("old", [31, 33, 35], STEADY), flow("new", [36, 37, 38], STEADY)) == \
        "new wins: its range is above old's"


def test_overlapping_ranges_are_no_win():
    """Record 0026's example: 34, 37, 38 against 31, 33, 35 is not a win."""
    assert call_winner(flow("old", [31, 33, 35], STEADY), flow("new", [34, 37, 38], STEADY)) == \
        "no win: the ranges overlap"


def test_touching_ranges_go_to_the_more_consistent_flow():
    assert call_winner(flow("old", [36, 37, 36], SHAKY), flow("new", [37, 38, 37], STEADY)) == \
        "new wins on the tiebreaker: the ranges touch and its runs are more consistent"
    assert call_winner(flow("old", [36, 37, 36], STEADY), flow("new", [37, 38, 37], STEADY)) == \
        "no win: the ranges touch and the consistency is equal"
