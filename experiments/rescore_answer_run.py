"""
Re-scores a saved answer run under the current code checks, and with --rejudge under the current judge rubric too.

Answers are never asked again, so a rubric or check change is measured on the same answers.
  - Without --rejudge: no API calls. The code checks run again; an answer that passes them keeps
    the judge's saved verdict, which came from the rubric at the time of the run.
  - With --rejudge: the code checks run again, and the judge grades every answer that passes them
    with the current rubric (one Sonnet call each, about $0.01). Its grades are saved apart, so the
    run's own grades are never overwritten, and compare_judge_with_my_grades --rejudged reads them.
Neither writes to evals/runs.jsonl: a re-score is not a new run.

  Input:  evals/answer_runs/<run>-answers.jsonl and <run>-grades.jsonl, evals/golden_questions.json,
          evals/refusal_probes.json, data/rule_chunks.json; with --rejudge, ANTHROPIC_API_KEY in .env
  Output: printed scores, then each failure; with --rejudge, evals/answer_runs/<run>-rejudged-grades.jsonl

Run from the project root:
    uv run python -m experiments.rescore_answer_run --run 20261107T1639-top5
    uv run python -m experiments.rescore_answer_run --run 20261107T1639-top5 --rejudge
"""

import argparse
import time

from anthropic import Anthropic

from answer.answer_shape import RulesAnswer
from app.settings import load_settings
from evals.answer_run_files import ANSWER_RUNS_FOLDER, append_line, read_lines
from evals.code_checks import find_code_failures
from evals.golden_answer_chunks import load_chunks, load_questions
from evals.probes import load_probes
from experiments.compare_answer_setups import (SECONDS_BETWEEN_QUESTIONS, check_and_grade, print_scores,
                                               summarise_answer_run)


# ===== Re-scoring with the saved verdicts =====

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


# ===== Re-scoring with the current judge =====

def rejudge_answer_lines(answer_lines: list[dict], question_by_id: dict[str, dict], chunks: list[dict],
                         run_name: str) -> dict[str, bool]:
    """Runs the code checks and the current judge on each saved answer, saves each grade line as it goes, and returns which answers passed."""
    settings = load_settings()
    anthropic_client = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    chunk_by_id = {chunk["id"]: chunk for chunk in chunks}

    # Start the rejudged grades file empty, then save each grade the moment it's done
    grades_path = ANSWER_RUNS_FOLDER / f"{run_name}-rejudged-grades.jsonl"
    grades_path.write_text("", encoding="utf-8")

    passed_by_id = {}
    for line in answer_lines:
        # A reply that didn't fit the shape stays a fail, with nothing to check or grade
        if line["is_format_error"]:
            grade_line = {"id": line["id"], "passed": False, "judged": False, "grade": None}
        else:
            print(f"judging {line['id']}")
            retrieved_chunks = [chunk_by_id[chunk_id] for chunk_id in line["retrieved_ids"]]
            rules_answer = RulesAnswer.model_validate(line["answer"])
            grade_line = check_and_grade(line, rules_answer, question_by_id[line["id"]], retrieved_chunks, chunks,
                                         chunk_by_id, anthropic_client, settings.claude_judge_model)
            if grade_line["judged"]:
                time.sleep(SECONDS_BETWEEN_QUESTIONS)
        append_line(grades_path, grade_line)
        passed_by_id[line["id"]] = grade_line["passed"]
    return passed_by_id


# ===== Running =====

def main() -> None:
    """Prints a saved run's scores under the current code checks, and with --rejudge under the current judge too."""
    parser = argparse.ArgumentParser(description="Re-score a saved answer run under the current code checks.")
    parser.add_argument("--run", required=True, help="the run name, such as 20261107T1639-top5")
    parser.add_argument("--rejudge", action="store_true", help="grade again with the current judge rubric (API calls)")
    arguments = parser.parse_args()

    # Load the saved answers, and the questions and clauses behind them
    answer_lines = read_lines(ANSWER_RUNS_FOLDER / f"{arguments.run}-answers.jsonl")
    question_by_id = {question["id"]: question for question in load_questions("dev") + load_probes()}
    chunks = load_chunks()

    # Score with the current judge, or with the verdicts the run saved
    if arguments.rejudge:
        passed_by_id = rejudge_answer_lines(answer_lines, question_by_id, chunks, arguments.run)
        print(f"{arguments.run}, re-judged with the current rubric (saved {arguments.run}-rejudged-grades.jsonl):")
    else:
        grade_lines = read_lines(ANSWER_RUNS_FOLDER / f"{arguments.run}-grades.jsonl")
        judge_passed_by_id = {line["id"]: line["passed"] for line in grade_lines}
        passed_by_id = rescore_answer_lines(answer_lines, judge_passed_by_id, question_by_id, chunks)
        print(f"{arguments.run}, re-scored under the current code checks (judge verdicts as saved):")
    print_scores(summarise_answer_run(answer_lines, passed_by_id), answer_lines, passed_by_id)


if __name__ == "__main__":
    main()
