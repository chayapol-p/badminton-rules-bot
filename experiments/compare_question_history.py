"""
Compares saved runs question by question: did a fix win its target questions, and did it break any other?

With 22 scored questions, a run's total moves by about 2 on its own, as much as one fix gains. So a
fix is judged on its target questions, across runs, and a full run is checked for regressions:
  - target questions: how often each passed in the baseline runs, and in the candidate runs
  - regressions: questions that passed in every baseline run but failed in a candidate run
  - gains: questions that failed in every baseline run but passed in every candidate run

  Input:  evals/answer_runs/<run>-grades.jsonl for each run, or <run>-rejudged-grades.jsonl with --rejudged
  Output: printed: the totals, the target questions, then every regression and gain

Run from the project root:
    uv run python -m experiments.compare_question_history --rejudged \\
        --baseline 20261108T1129-top5-cap16k --candidate 20261108T1203-top5-list-items \\
        --target wheelchair-shuttle-on-net
"""

import argparse

from evals.answer_run_files import ANSWER_RUNS_FOLDER, read_lines


# ===== Reading the runs =====

def read_passed_by_id(run_name: str, uses_rejudged: bool) -> dict[str, bool]:
    """Returns whether each question passed in one saved run."""
    grades_suffix = "grades"
    if uses_rejudged:
        grades_suffix = "rejudged-grades"
    grade_lines = read_lines(ANSWER_RUNS_FOLDER / f"{run_name}-{grades_suffix}.jsonl")
    return {line["id"]: line["passed"] for line in grade_lines}


def count_passes(question_id: str, runs: list[dict[str, bool]]) -> int:
    """Returns in how many of the runs the question passed."""
    return sum(1 for passed_by_id in runs if passed_by_id[question_id])


# ===== Comparing =====

def compare_runs(baseline_runs: list[dict[str, bool]], candidate_runs: list[dict[str, bool]]) -> dict:
    """Returns the questions that regressed (always passed before, failed now) and gained (always failed before, always pass now)."""
    regressions = []
    gains = []
    for question_id in sorted(baseline_runs[0]):
        baseline_passes = count_passes(question_id, baseline_runs)
        candidate_passes = count_passes(question_id, candidate_runs)
        always_passed_before = baseline_passes == len(baseline_runs)
        never_passed_before = baseline_passes == 0
        if always_passed_before and candidate_passes < len(candidate_runs):
            regressions.append(question_id)
        if never_passed_before and candidate_passes == len(candidate_runs):
            gains.append(question_id)
    return {"regressions": regressions, "gains": gains}


def describe_passes(question_id: str, runs: list[dict[str, bool]]) -> str:
    """Returns how often a question passed, such as "2 of 3"."""
    return f"{count_passes(question_id, runs)} of {len(runs)}"


# ===== Running =====

def main() -> None:
    """Prints the target questions, the regressions and the gains between two groups of runs."""
    parser = argparse.ArgumentParser(description="Compare saved runs question by question.")
    parser.add_argument("--baseline", nargs="+", required=True, help="run names without the fix")
    parser.add_argument("--candidate", nargs="+", required=True, help="run names with the fix")
    parser.add_argument("--target", nargs="*", default=[], help="the question ids the fix is meant to win")
    parser.add_argument("--rejudged", action="store_true", help="read the runs' rejudged grades")
    arguments = parser.parse_args()

    # Read both groups of runs
    baseline_runs = [read_passed_by_id(run_name, arguments.rejudged) for run_name in arguments.baseline]
    candidate_runs = [read_passed_by_id(run_name, arguments.rejudged) for run_name in arguments.candidate]

    # The totals, for reference only: they move by about 2 on their own
    baseline_totals = [sum(passed_by_id.values()) for passed_by_id in baseline_runs]
    candidate_totals = [sum(passed_by_id.values()) for passed_by_id in candidate_runs]
    print(f"passed, all questions: baseline {baseline_totals}, candidate {candidate_totals}")

    # The target questions, then what changed elsewhere
    for question_id in arguments.target:
        print(f"target {question_id}: baseline {describe_passes(question_id, baseline_runs)}, "
              f"candidate {describe_passes(question_id, candidate_runs)}")
    comparison = compare_runs(baseline_runs, candidate_runs)
    print(f"regressions (always passed before, failed now): {', '.join(comparison['regressions']) or 'none'}")
    print(f"gains (always failed before, always pass now): {', '.join(comparison['gains']) or 'none'}")


if __name__ == "__main__":
    main()
