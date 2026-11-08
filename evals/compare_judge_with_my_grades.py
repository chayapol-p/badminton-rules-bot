"""
Compares your own grades with the judge's grades for one answer run, and lists every disagreement.

Grade before you open the run's -grades.jsonl file, so the judge's verdict can't steer yours.

  Input:  evals/human_grades.jsonl, one line per answer you graded:
            {"run": "20261107T1200-top5", "id": "deuce-end", "passed": true, "reason": "Gives both the 2-point lead and the 30-point cap."}
          evals/answer_runs/<run>-grades.jsonl, written by experiments.compare_answer_setups
  Output: printed: how many grades match, then each disagreement with both reasons

Trust the judge when it matches at least 9 of your 10 grades (a starting bar). Below that, fix
the rubric line behind the disagreements and regrade. An answer the code checks failed was never
sent to the judge, so it is listed apart and left out of the count.

Run from the project root:
    uv run python -m evals.compare_judge_with_my_grades --run 20261107T1200-top5
"""

import argparse
import json
from pathlib import Path


# Constants
## Path to each resource
EVALS_FOLDER = Path(__file__).resolve().parent
HUMAN_GRADES_FILE = EVALS_FOLDER / "human_grades.jsonl"
ANSWER_RUNS_FOLDER = EVALS_FOLDER / "answer_runs"


# ===== Reading grade files =====

def read_lines(path: Path) -> list[dict]:
    """Returns one dictionary per non-empty line of a JSON Lines file."""
    lines = []
    for text_line in path.read_text(encoding="utf-8").splitlines():
        if text_line.strip():
            lines.append(json.loads(text_line))
    return lines


# ===== Comparing =====

def judge_reasons(grade_line: dict) -> str:
    """Returns the reasons of the rubric lines the judge failed, or its pass when it failed none."""
    failed_reasons = []
    for line_name, rubric_line in grade_line["grade"].items():
        if not rubric_line["passed"]:
            failed_reasons.append(f"{line_name}: {rubric_line['reason']}")
    if not failed_reasons:
        return "every rubric line passed"
    return " | ".join(failed_reasons)


def compare_grades(my_grades: list[dict], judge_grade_by_id: dict[str, dict]) -> dict:
    """Returns how many of your grades the judge matched, each disagreement with both reasons, and the answers it never graded."""
    disagreements = []
    not_judged_ids = []
    for my_grade in my_grades:
        judge_grade = judge_grade_by_id[my_grade["id"]]

        # No grade means the code checks failed the answer before the judge saw it
        if judge_grade["grade"] is None:
            not_judged_ids.append(my_grade["id"])
            continue
        if judge_grade["passed"] != my_grade["passed"]:
            disagreements.append({
                "id": my_grade["id"],
                "mine": my_grade["passed"],
                "my_reason": my_grade["reason"],
                "judge": judge_grade["passed"],
                "judge_reason": judge_reasons(judge_grade),
            })
    compared_count = len(my_grades) - len(not_judged_ids)
    return {"matched": compared_count - len(disagreements), "graded": compared_count,
            "disagreements": disagreements, "not_judged_ids": not_judged_ids}


# ===== Running =====

def main() -> None:
    """Prints the agreement between your grades and the judge's for one run."""
    parser = argparse.ArgumentParser(description="Compare your grades with the judge's for one answer run.")
    parser.add_argument("--run", required=True, help="the run name, such as 20261107T1200-top5")
    arguments = parser.parse_args()

    # Your grades for this run, leaving out lines still waiting for a grade, and the judge's grades by question id
    run_grades = [grade for grade in read_lines(HUMAN_GRADES_FILE) if grade["run"] == arguments.run]
    my_grades = [grade for grade in run_grades if grade["passed"] is not None]
    ungraded_count = len(run_grades) - len(my_grades)
    if ungraded_count:
        print(f"{ungraded_count} lines still have \"passed\": null and are left out")
    judge_lines = read_lines(ANSWER_RUNS_FOLDER / f"{arguments.run}-grades.jsonl")
    judge_grade_by_id = {line["id"]: line for line in judge_lines}

    comparison = compare_grades(my_grades, judge_grade_by_id)
    print(f"judge matches {comparison['matched']} of your {comparison['graded']} grades")
    if comparison["not_judged_ids"]:
        print(f"not judged, failed by the code checks: {', '.join(comparison['not_judged_ids'])}")
    for disagreement in comparison["disagreements"]:
        print(f"\n{disagreement['id']}: you {disagreement['mine']}, judge {disagreement['judge']}")
        print(f"  you:   {disagreement['my_reason']}")
        print(f"  judge: {disagreement['judge_reason']}")


if __name__ == "__main__":
    main()
