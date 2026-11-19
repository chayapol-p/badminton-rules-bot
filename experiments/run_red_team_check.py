"""
Red-team run for the badminton-wide topic check: a sneaky user tries to trick the check and the bot
(evals/red_team_questions.json, Job's request, 18 Nov 2026).

Part A: the real check on every question, 3 runs, one question at a time. Part B: the full real bot once per
question, to see the off-topic reply come back fast for blocked questions and what the flow does with passed ones.
Each run appends one line to evals/runs.jsonl under the stage "red-team". The command stops before a call once the
cost passes the cap.

  Input:  evals/red_team_questions.json; data/ (the chunks and their saved vectors); MISTRAL_API_KEY
  Output: one line per run in evals/runs.jsonl, and a printed table

Run from the project root:
    uv run python -m experiments.run_red_team_check                # check runs, then the full bot once
    uv run python -m experiments.run_red_team_check --check-only   # check runs alone
"""

import argparse
import json
import time
from datetime import datetime, timezone

from answer_flows.rules_bot import RulesBot
from answer_flows.shared.mistral_client import build_mistral_client
from answer_flows.topic_screen import CHECK_TIMEOUT_MS, TOPIC_CHECK_PROMPT, build_mistral_topic_check
from evals.log_eval_run import append_run
from experiments.run_answer_experiment import read_code_version
from experiments.run_topic_check_eval import (CostTracker, RecordingClient, answer_one_question, check_one_question,
                                              percentile)
from retrieval.expand_with_rule_links import load_rule_map
from retrieval.load_rule_chunks import PROJECT_FOLDER, load_chunks
from retrieval.retrieve_sources import build_live_vector_search
from settings import load_settings


# Constants
## How many check runs, the cost at which the command stops (Job, 18 Nov), and the stage runs.jsonl records
CHECK_RUN_COUNT = 3
COST_CAP_DOLLARS = 1.00
MEASUREMENT_STAGE = "red-team"

## The red-team questions
RED_TEAM_FILE = PROJECT_FOLDER / "evals" / "red_team_questions.json"


# Returns the red-team questions, each with the fields the shared check and answer helpers read
def load_red_team_questions() -> list[dict]:
    questions = json.loads(RED_TEAM_FILE.read_text(encoding="utf-8"))["questions"]
    return [{**question, "set": "red_team"} for question in questions]


# Runs the check on every question, CHECK_RUN_COUNT times, one at a time, and logs each run under the given stage
def run_check_part(questions: list[dict], recording_client: RecordingClient, settings, cost_tracker: CostTracker,
                   stage: str = MEASUREMENT_STAGE, run_label: str = "red-team-check") -> list[list[dict]]:
    topic_check = build_mistral_topic_check(recording_client, settings.mistral_draft_model)
    all_runs = []
    for run_number in range(1, CHECK_RUN_COUNT + 1):
        started = time.perf_counter()
        rows = [check_one_question(question, topic_check, recording_client, cost_tracker) for question in questions]
        scores = {"tricks_that_worked": sorted(row["id"] for row in rows if row["verdict"] != row["expected_screen"]),
                  "failed_open": sorted(row["id"] for row in rows if row["error"] is not None),
                  "questions": len(rows), "cost_dollars": round(sum(row["cost"] for row in rows), 5),
                  "rows": [{"id": row["id"], "expected": row["expected_screen"], "verdict": row["verdict"],
                            "seconds": round(row["seconds"], 2), "error": row["error"]} for row in rows]}
        run_settings = {"run": f"{datetime.now(timezone.utc):%Y%m%dT%H%M}-{run_label}-run{run_number}",
                        "part": "check", "model": settings.mistral_draft_model, "temperature": 0,
                        "timeout_ms": CHECK_TIMEOUT_MS, "retries": "none", "prompt": TOPIC_CHECK_PROMPT,
                        "questions": len(questions), "questions_at_once": 1}
        run_settings.update(read_code_version())
        append_run(stage, run_settings, scores, round(time.perf_counter() - started, 2))
        seconds = [row["seconds"] for row in rows]
        print(f"check run {run_number}: p50 {percentile(seconds, 50):.2f} s · p95 {percentile(seconds, 95):.2f} s")
        print(f"check run {run_number}: tricks that worked {scores['tricks_that_worked']} · "
              f"failed open {scores['failed_open']} · ${scores['cost_dollars']:.4f}", flush=True)
        all_runs.append(rows)
    return all_runs


# Answers every question once with the full real bot, one at a time, and logs the run
def run_answer_part(questions: list[dict], recording_client: RecordingClient, settings,
                    cost_tracker: CostTracker) -> list[dict]:
    # Built like load_rules_bot(), with the recording client so each call's cost is counted
    chunks = load_chunks()
    live_search = build_live_vector_search(chunks, recording_client, settings.mistral_embedding_model)
    topic_check = build_mistral_topic_check(recording_client, settings.mistral_draft_model)
    rules_bot = RulesBot(recording_client, settings, chunks, load_rule_map(), live_search.search,
                         is_rules_question=topic_check)

    started = time.perf_counter()
    rows = [answer_one_question(question, rules_bot, recording_client, cost_tracker) for question in questions]
    scores = {"questions": len(rows), "cost_dollars": round(sum(row["cost"] for row in rows), 4),
              "rows": [{key: row[key] for key in ("id", "refused", "refusal_kind", "seconds", "error", "answer")}
                       for row in rows]}
    run_settings = {"run": f"{datetime.now(timezone.utc):%Y%m%dT%H%M}-red-team-answers", "part": "answers",
                    "check_model": settings.mistral_draft_model, "answer_model": settings.mistral_answer_model,
                    "reasoning_effort": settings.mistral_reasoning_effort, "flow": "gather-then-write",
                    "setup": "hybrid", "questions": len(questions), "questions_at_once": 1}
    run_settings.update(read_code_version())
    append_run(MEASUREMENT_STAGE, run_settings, scores, round(time.perf_counter() - started, 2))
    return rows


# Prints one line per question: expected, the check's verdict per run, and the bot's outcome
def print_table(check_runs: list[list[dict]], answer_rows: list[dict]) -> None:
    print("\n=== red team")
    for question_number, answer_row in enumerate(answer_rows):
        verdicts = [rows[question_number]["verdict"] for rows in check_runs]
        expected = check_runs[0][question_number]["expected_screen"]
        print(f"{answer_row['id']:<18} expected {expected:<9} check {verdicts} · bot refused={answer_row['refused']} "
              f"kind={answer_row['refusal_kind']} {answer_row['seconds']} s")
        print(f"    answer: {answer_row['answer'][:300]!r}")


# Runs both parts under one cost cap
def main() -> None:
    parser = argparse.ArgumentParser(description="Red-team the topic check with paid calls.")
    parser.add_argument("--check-only", action="store_true", help="skip the full bot")
    arguments = parser.parse_args()

    settings = load_settings()
    recording_client = RecordingClient(build_mistral_client(settings))
    cost_tracker = CostTracker(COST_CAP_DOLLARS)
    questions = load_red_team_questions()
    check_runs = run_check_part(questions, recording_client, settings, cost_tracker)
    if not arguments.check_only:
        answer_rows = run_answer_part(questions, recording_client, settings, cost_tracker)
        print_table(check_runs, answer_rows)
    print(f"\ntotal cost ${cost_tracker.spent_dollars:.4f}", flush=True)


if __name__ == "__main__":
    main()
