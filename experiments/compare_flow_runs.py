"""
Calls a win between two flows from their saved runs (records 0026 and 0027): each run's combined metric, each
flow's range over its runs, and each flow's consistency.

  win          the flows' ranges of the combined metric don't overlap
  tiebreaker   when the ranges only touch (one flow's lowest equals the other's highest), the flow with the higher
               consistency wins; equal consistency is no win
  consistency  the share of questions with the same gate verdict (passed or failed) in all of a flow's runs

Only runs with a scorecard (record 0027) can be compared; older runs keep their overall pass counts.

  Input:  evals/answer_runs/<run>-grades.jsonl for each run
  Output: printed: each run's metric and gate count, each flow's range and consistency, then the verdict

Run from the project root:
    uv run python -m experiments.compare_flow_runs \\
        --flow-a natural 20261117T0318-hybrid-natural-phase2-run1 … \\
        --flow-b per-part 20261117T0340-hybrid-per-part-phase2-run1 …
"""

import argparse
from dataclasses import dataclass

from evals.answer_run_files import ANSWER_RUNS_FOLDER, read_lines
from evals.scorecard import summarise_scorecards


# ===== One flow's runs =====

@dataclass
class FlowRuns:
    """One flow's runs: each run's combined metric and gate count, and each question's gate verdict per run."""

    name: str
    run_names: list[str]
    combined_metrics: list[float]
    gate_passed_counts: list[int]
    passed_by_id_per_run: list[dict[str, bool]]


def read_flow_runs(name: str, run_names: list[str]) -> FlowRuns:
    """Returns one flow's runs read from their grade files; stops when a run has no scorecard to compare."""
    combined_metrics = []
    gate_passed_counts = []
    passed_by_id_per_run = []
    for run_name in run_names:
        grade_lines = read_lines(ANSWER_RUNS_FOLDER / f"{run_name}-grades.jsonl")

        # A run from before the scorecard can't be read on the combined metric, and the comparison depends on it
        if "scorecard" not in grade_lines[0]:
            raise SystemExit(f"{run_name} has no scorecard (a run from before record 0027)")
        run_scorecard = summarise_scorecards(grade_lines)
        combined_metrics.append(run_scorecard["combined_metric"])
        gate_passed_counts.append(run_scorecard["gate_passed"])
        passed_by_id_per_run.append({line["id"]: line["scorecard"]["passed"] for line in grade_lines})
    return FlowRuns(name=name, run_names=run_names, combined_metrics=combined_metrics,
                    gate_passed_counts=gate_passed_counts, passed_by_id_per_run=passed_by_id_per_run)


def measure_consistency(flow_runs: FlowRuns) -> float:
    """Returns the share of questions whose gate verdict is the same in all of the flow's runs."""
    question_ids = flow_runs.passed_by_id_per_run[0].keys()
    same_verdict_count = 0
    for question_id in question_ids:
        verdicts = {passed_by_id[question_id] for passed_by_id in flow_runs.passed_by_id_per_run}
        if len(verdicts) == 1:
            same_verdict_count += 1
    return round(same_verdict_count / len(question_ids), 3)


# ===== The verdict =====

def call_winner(flow_a: FlowRuns, flow_b: FlowRuns) -> str:
    """Returns the verdict: a flow's win, a win on the tiebreaker, or no win."""
    lowest_a, highest_a = min(flow_a.combined_metrics), max(flow_a.combined_metrics)
    lowest_b, highest_b = min(flow_b.combined_metrics), max(flow_b.combined_metrics)

    # Ranges apart: the higher range wins
    if highest_a < lowest_b:
        return f"{flow_b.name} wins: its range is above {flow_a.name}'s"
    if highest_b < lowest_a:
        return f"{flow_a.name} wins: its range is above {flow_b.name}'s"

    # Ranges that only touch go to the tiebreaker; any wider overlap is no win
    ranges_touch = highest_a == lowest_b or highest_b == lowest_a
    if not ranges_touch:
        return "no win: the ranges overlap"
    consistency_a = measure_consistency(flow_a)
    consistency_b = measure_consistency(flow_b)
    if consistency_a == consistency_b:
        return "no win: the ranges touch and the consistency is equal"
    winner = flow_a
    if consistency_b > consistency_a:
        winner = flow_b
    return f"{winner.name} wins on the tiebreaker: the ranges touch and its runs are more consistent"


# ===== Printing =====

def print_flow_runs(flow_runs: FlowRuns) -> None:
    """Prints one flow's runs, its range and its consistency."""
    print(f"{flow_runs.name}")
    for run_name, metric, gate_passed in zip(flow_runs.run_names, flow_runs.combined_metrics, flow_runs.gate_passed_counts):
        print(f"  {run_name}  metric {metric}  · gate passed {gate_passed}")
    print(f"  range {min(flow_runs.combined_metrics)}–{max(flow_runs.combined_metrics)}  "
          f"· consistency {measure_consistency(flow_runs)}")


def main() -> None:
    """Reads both flows' runs, prints them and calls the verdict."""
    parser = argparse.ArgumentParser(description="Call a win between two flows on the combined metric's ranges.")
    parser.add_argument("--flow-a", nargs="+", required=True, metavar="NAME_THEN_RUNS")
    parser.add_argument("--flow-b", nargs="+", required=True, metavar="NAME_THEN_RUNS")
    arguments = parser.parse_args()
    flow_a = read_flow_runs(arguments.flow_a[0], arguments.flow_a[1:])
    flow_b = read_flow_runs(arguments.flow_b[0], arguments.flow_b[1:])
    print_flow_runs(flow_a)
    print_flow_runs(flow_b)
    print(call_winner(flow_a, flow_b))


if __name__ == "__main__":
    main()
