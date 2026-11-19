"""
Runs the topic check alone on the casual rules questions (evals/casual_rules_questions.json): short rules questions
that name no sport, one per rule heading. Every one must pass. Job's request, 18 Nov 2026 (option 4).

3 runs, one question at a time; each run appends one line to evals/runs.jsonl under the stage given on the command
line, so the runs before and after a prompt change sit side by side. Stops before a call once the cost passes the cap.

  Input:  evals/casual_rules_questions.json; MISTRAL_API_KEY
  Output: one line per run in evals/runs.jsonl, and the blocked questions printed per run

Run from the project root:
    uv run python -m experiments.run_casual_rules_check --stage casual-rules-baseline
"""

import argparse
import json

from answer_flows.shared.mistral_client import build_mistral_client
from experiments.run_red_team_check import run_check_part
from experiments.run_topic_check_eval import CostTracker, RecordingClient
from retrieval.load_rule_chunks import PROJECT_FOLDER
from settings import load_settings


# Constants
## The cost at which the command stops (Job, 18 Nov: $0.50 for all of option 1 + 4)
COST_CAP_DOLLARS = 0.50

## The casual rules questions
CASUAL_RULES_FILE = PROJECT_FOLDER / "evals" / "casual_rules_questions.json"


# Returns the casual questions, each with the fields the shared check helpers read; every one must pass
def load_casual_rules_questions() -> list[dict]:
    questions = json.loads(CASUAL_RULES_FILE.read_text(encoding="utf-8"))["questions"]
    return [{**question, "set": "casual_rules", "expected_screen": "on_topic"} for question in questions]


# Runs the check runs and prints every blocked question with its text
def main() -> None:
    parser = argparse.ArgumentParser(description="Run the topic check on the casual rules questions.")
    parser.add_argument("--stage", required=True, help="the stage runs.jsonl records")
    arguments = parser.parse_args()

    settings = load_settings()
    recording_client = RecordingClient(build_mistral_client(settings))
    cost_tracker = CostTracker(COST_CAP_DOLLARS)
    questions = load_casual_rules_questions()
    check_runs = run_check_part(questions, recording_client, settings, cost_tracker, stage=arguments.stage,
                                run_label="casual-rules-check")

    for run_number, rows in enumerate(check_runs, start=1):
        blocked_rows = [row for row in rows if row["verdict"] == "off_topic"]
        print(f"\n=== run {run_number}: {len(blocked_rows)} of {len(rows)} blocked")
        for row in blocked_rows:
            print(f"  {row['source']:<32} {row['question']}")
    print(f"\ntotal cost ${cost_tracker.spent_dollars:.4f}", flush=True)


if __name__ == "__main__":
    main()
