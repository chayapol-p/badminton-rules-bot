"""
Re-scores a saved answer run under the current code checks, with no API calls and no log line.

The code checks (evals/code_checks.py) run again on the saved answers. An answer that passes
them keeps the judge's saved verdict; an answer that fails them has failed. Use it when the
code checks change, to see what the new checks would have done to a past run. The judge's
verdicts come from its rubric at the time of the run, so a fresh run is still the real score.

  Input:  evals/answer_runs/<run>-answers.jsonl and <run>-grades.jsonl, evals/golden_questions.json,
          evals/refusal_probes.json, data/rule_chunks.json
  Output: printed scores, then each failure; nothing is written

Run from the project root:
    uv run python -m experiments.rescore_answer_run --run 20261107T1639-top5
"""

import argparse

from evals.code_checks import find_code_failures
from evals.compare_judge_with_my_grades import ANSWER_RUNS_FOLDER, read_lines
from evals.golden_answer_chunks import load_chunks, load_questions
from evals.refusal_probes import load_refusal_probes
from experiments.compare_answer_setups import print_scores, summarise_answer_run


# ===== Re-scoring =====

def rescore_answer_lines(answer_lines: list[dict], judge_passed_by_id: dict[str, bool],
                         question_by_id: dict[str, dict], chunks: list[dict]) -> dict[str, bool]:
    """Adds the code checks' failures and warnings to each answer line, and returns which answers pass the code checks and the saved judge verdict."""
    chunk_by_id = {chunk["id"]: chunk for chunk in chunks}
    passed_by_id = {}
    for line in answer_lines:
        failures, warnings = find_code_failures(line, question_by_id[line["id"]], chunks, chunk_by_id)
        line["code_failures"] = failures
        line["code_warnings"] = warnings
        is_code_clean = not failures
        passed_by_id[line["id"]] = is_code_clean and judge_passed_by_id[line["id"]]
    return passed_by_id


# ===== Running =====

def main() -> None:
    """Prints a saved run's scores under the current code checks."""
    parser = argparse.ArgumentParser(description="Re-score a saved answer run under the current code checks.")
    parser.add_argument("--run", required=True, help="the run name, such as 20261107T1639-top5")
    arguments = parser.parse_args()

    # Load the saved answers and the judge's saved verdicts, and the questions and clauses behind them
    answer_lines = read_lines(ANSWER_RUNS_FOLDER / f"{arguments.run}-answers.jsonl")
    grade_lines = read_lines(ANSWER_RUNS_FOLDER / f"{arguments.run}-grades.jsonl")
    judge_passed_by_id = {line["id"]: line["passed"] for line in grade_lines}
    question_by_id = {question["id"]: question for question in load_questions("dev") + load_refusal_probes()}

    passed_by_id = rescore_answer_lines(answer_lines, judge_passed_by_id, question_by_id, load_chunks())
    print(f"{arguments.run}, re-scored under the current code checks (judge verdicts as saved):")
    print_scores(summarise_answer_run(answer_lines, passed_by_id), answer_lines, passed_by_id)


if __name__ == "__main__":
    main()
