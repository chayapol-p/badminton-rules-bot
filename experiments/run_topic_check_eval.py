"""
Measures the topic check of slice 7 (docs/specs/refuse-off-topic-questions-fast.md) with paid calls, in two parts.

Part A, the check alone (criteria 2 and 3): the real check (answer_flows/topic_screen.py, the approved prompt) on every
question of every set, 3 runs. It counts the off-topic questions caught, the near misses let through, the rules
questions wrongly blocked, and the checks that failed open, with latency and cost.
Part B, full answers (criterion 4): the real bot, check and flow, on every on-topic question that should be refused,
3 runs. It records each answer's refusal_kind, and which answers change across the runs.

The held-out golden questions are left out of both parts: they are scored once, for the published number (CLAUDE.md,
experiment rule 4), and a measurement that may tune the check's prompt must not see them.

Each run appends one line to evals/runs.jsonl. The whole command stops before a call once the cost passes the cap.
Costs count the chat calls; the few embedding calls of part B's searches are left out (a fraction of a cent).

  Input:  evals/*_questions.json and the probes; data/ (the chunks and their saved vectors); MISTRAL_API_KEY
  Output: one line per run in evals/runs.jsonl, and a printed table per run

Run from the project root:
    uv run python -m experiments.run_topic_check_eval                          # both parts, 4 questions at once
    uv run python -m experiments.run_topic_check_eval --part check --parallel 1  # part A alone, one at a time

One at a time keeps under Mistral's rate limit: on 18 Nov, 4 at once got 429 on every check of runs 2 and 3.
"""

import argparse
import json
import statistics
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

from mistralai.client import Mistral

from answer_flows.rules_bot import RulesBot
from answer_flows.shared.mistral_client import build_mistral_client
from answer_flows.topic_screen import (CHECK_TIMEOUT_MS, TOPIC_CHECK_PROMPT, build_mistral_topic_check)
from app.settings import load_settings
from evals.golden_answer_chunks import PROJECT_FOLDER, load_chunks, load_questions
from evals.log_eval_run import append_run
from evals.probes import load_false_premise_probes, load_phase2_questions, load_refusal_probes, load_unseen_questions
from evals.token_costs import call_cost
from experiments.run_answer_experiment import read_code_version
from retrieval.expand_with_rule_links import load_rule_map
from retrieval.retrieve_sources import build_live_vector_search


# Constants
## How many runs per part (experiment rule 5), questions at once, and the cost at which the command stops
RUN_COUNT = 3
QUESTIONS_AT_ONCE = 4
COST_CAP_DOLLARS = 3.00

## The stage runs.jsonl records, so these lines are read only against each other
MEASUREMENT_STAGE = "slice7-topic-check"

## The refusal probes that get the off-topic reply: none since the badminton-wide relabel (Job, 18 Nov), when the
## training plan, the result and the history probes moved to the flow
OFF_TOPIC_PROBE_IDS: set[str] = set()


# ===== Recording each call's tokens =====

@dataclass
class CallRecord:
    """One chat call: its model and tokens."""

    model: str
    input_tokens: int
    output_tokens: int


class RecordingClient:
    """Wraps the Mistral client and records every chat call's tokens, per thread, so parallel questions don't mix."""

    def __init__(self, mistral_client: Mistral):
        self.mistral_client = mistral_client
        self.embeddings = mistral_client.embeddings
        self.thread_calls = threading.local()
        self.chat = self

    def complete(self, **request):
        """Sends the chat call and records its model and tokens for the calling thread."""
        response = self.mistral_client.chat.complete(**request)
        self.calls_for_this_thread().append(CallRecord(request["model"], response.usage.prompt_tokens,
                                                       response.usage.completion_tokens))
        return response

    def calls_for_this_thread(self) -> list[CallRecord]:
        """Returns the calling thread's list of calls, starting one when it has none."""
        if not hasattr(self.thread_calls, "calls"):
            self.thread_calls.calls = []
        return self.thread_calls.calls

    def take_calls(self) -> list[CallRecord]:
        """Returns the calling thread's calls so far and starts a fresh list."""
        calls = self.calls_for_this_thread()
        self.thread_calls.calls = []
        return calls


# Returns the cost of a list of calls in US dollars
def cost_of_calls(calls: list[CallRecord]) -> float:
    return sum(call_cost(call.model, call.input_tokens, call.output_tokens) for call in calls)


# ===== The cost cap =====

class CostTracker:
    """Adds up the cost of every call across both parts, and says when the cap is passed."""

    def __init__(self, cap_dollars: float):
        self.cap_dollars = cap_dollars
        self.spent_dollars = 0.0
        self.lock = threading.Lock()

    def add(self, dollars: float) -> None:
        """Adds one question's cost."""
        with self.lock:
            self.spent_dollars += dollars

    def is_over_cap(self) -> bool:
        """True once the spending passes the cap."""
        return self.spent_dollars > self.cap_dollars


class CostCapReached(RuntimeError):
    """The command spent more than the cap; the parts stop before their next call."""


# ===== The questions =====

# Returns every question the check is measured on, each with the screen result the plan expects
def load_check_questions() -> list[dict]:
    off_topic_questions = json_questions("off_topic_questions")
    questions = []
    for question in off_topic_questions:
        questions.append({"id": question["id"], "set": "off_topic", "question": question["question"],
                          "expected_screen": question["expected_screen"], "kind": question["kind"]})

    # Every question in the other sets is about the rules, except the three probes the plan sends to the reply
    rules_sets = [("golden_dev", load_questions("dev")), ("unseen", load_unseen_questions()),
                  ("phase2", load_phase2_questions()), ("refusal_probes", load_refusal_probes()),
                  ("false_premise_probes", load_false_premise_probes())]
    for set_name, set_questions in rules_sets:
        for question in set_questions:
            is_off_topic_probe = question["id"] in OFF_TOPIC_PROBE_IDS
            expected_screen = "off_topic" if is_off_topic_probe else "on_topic"
            questions.append({"id": question["id"], "set": set_name, "question": question["question"],
                              "expected_screen": expected_screen, "kind": question.get("category", "")})
    return questions


# Returns the questions of one set file in evals/
def json_questions(file_name: str) -> list[dict]:
    return json.loads((PROJECT_FOLDER / "evals" / f"{file_name}.json").read_text(encoding="utf-8"))["questions"]


# Returns the badminton questions that should be refused (criterion 4): the no-answer questions about the rules,
# and the badminton questions that aren't rules
def load_refusal_questions() -> list[dict]:
    rules_sets = [("golden_dev", load_questions("dev")), ("unseen", load_unseen_questions()),
                  ("phase2", load_phase2_questions()), ("refusal_probes", load_refusal_probes())]
    questions = []
    for set_name, set_questions in rules_sets:
        for question in set_questions:
            # The attacks have no fixed answer but want cited rules, and the off-topic probes take the reply
            is_no_answer = question["answer"] is None and question["category"] != "attack"
            if is_no_answer and question["id"] not in OFF_TOPIC_PROBE_IDS:
                questions.append({"id": question["id"], "set": set_name, "question": question["question"]})

    # The badminton questions that aren't rules go to the flow since the badminton-wide relabel (Job, 18 Nov)
    for question in json_questions("off_topic_questions"):
        if question["kind"] == "badminton_not_rules":
            questions.append({"id": question["id"], "set": "off_topic", "question": question["question"]})
    return questions


# ===== Part A: the check alone =====

# Runs the check on one question and returns its verdict, seconds, cost and any error; a failed check counts as
# "on_topic", as the bot lets it through (criterion 5)
def check_one_question(question: dict, topic_check, recording_client: RecordingClient, cost_tracker: CostTracker) -> dict:
    if cost_tracker.is_over_cap():
        raise CostCapReached(f"spent ${cost_tracker.spent_dollars:.2f}, over the ${COST_CAP_DOLLARS:.2f} cap")
    started = time.perf_counter()
    error_text = None
    try:
        is_rules_question = topic_check(question["question"])
        verdict = "on_topic" if is_rules_question else "off_topic"
    except Exception as error:
        verdict = "on_topic"
        error_text = f"{type(error).__name__}: {error}"
    seconds = time.perf_counter() - started
    cost = cost_of_calls(recording_client.take_calls())
    cost_tracker.add(cost)
    return {**question, "verdict": verdict, "seconds": seconds, "cost": cost, "error": error_text}


# Returns the p-th percentile of a list of seconds (p50, p95), by the nearest-rank rule
def percentile(values: list[float], percent: int) -> float:
    ordered = sorted(values)
    rank = max(1, round(percent / 100 * len(ordered)))
    return ordered[rank - 1]


# Returns one check run's scores from its rows
def score_check_run(rows: list[dict]) -> dict:
    off_topic_rows = [row for row in rows if row["set"] == "off_topic" and row["expected_screen"] == "off_topic"]
    near_miss_rows = [row for row in rows if row["set"] == "off_topic" and row["expected_screen"] == "on_topic"]
    rules_rows = [row for row in rows if row["set"] != "off_topic" and row["expected_screen"] == "on_topic"]
    probe_rows = [row for row in rows if row["set"] != "off_topic" and row["expected_screen"] == "off_topic"]
    seconds = [row["seconds"] for row in rows]
    return {
        "off_topic_caught": sum(row["verdict"] == "off_topic" for row in off_topic_rows),
        "off_topic_questions": len(off_topic_rows),
        "near_misses_let_through": sum(row["verdict"] == "on_topic" for row in near_miss_rows),
        "near_misses": len(near_miss_rows),
        "rules_questions_blocked": sorted(row["id"] for row in rules_rows if row["verdict"] == "off_topic"),
        "rules_questions": len(rules_rows),
        "off_topic_probes_caught": sum(row["verdict"] == "off_topic" for row in probe_rows),
        "off_topic_probes": len(probe_rows),
        "missed_off_topic": sorted(row["id"] for row in off_topic_rows if row["verdict"] == "on_topic"),
        "blocked_near_misses": sorted(row["id"] for row in near_miss_rows if row["verdict"] == "off_topic"),
        "failed_open": sorted(f"{row['id']} ({row['error']})" for row in rows if row["error"] is not None),
        "p50_seconds": round(statistics.median(seconds), 2),
        "p95_seconds": round(percentile(seconds, 95), 2),
        "cost_dollars": round(sum(row["cost"] for row in rows), 5),
    }


# Runs the check on every question, RUN_COUNT times, and logs and prints each run
def run_check_part(recording_client: RecordingClient, settings, cost_tracker: CostTracker,
                   questions_at_once: int) -> list[dict]:
    questions = load_check_questions()
    topic_check = build_mistral_topic_check(recording_client, settings.mistral_draft_model)
    run_scores = []
    for run_number in range(1, RUN_COUNT + 1):
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=questions_at_once) as executor:
            rows = list(executor.map(lambda question: check_one_question(question, topic_check, recording_client,
                                                                         cost_tracker), questions))
        scores = score_check_run(rows)
        scores["rows"] = [{"id": row["id"], "set": row["set"], "expected": row["expected_screen"],
                           "verdict": row["verdict"], "seconds": round(row["seconds"], 2), "error": row["error"]}
                          for row in rows]
        run_settings = {"run": f"{datetime.now(timezone.utc):%Y%m%dT%H%M}-topic-check-run{run_number}", "part": "check",
                        "model": settings.mistral_draft_model,
                        "temperature": 0, "timeout_ms": CHECK_TIMEOUT_MS, "retries": "none",
                        "prompt": TOPIC_CHECK_PROMPT, "questions": len(questions),
                        "held_out_left_out": True, "questions_at_once": questions_at_once}
        run_settings.update(read_code_version())
        append_run(MEASUREMENT_STAGE, run_settings, scores, round(time.perf_counter() - started, 2))
        print_check_run(run_number, scores)
        run_scores.append(scores)
    return run_scores


# Prints one check run's results
def print_check_run(run_number: int, scores: dict) -> None:
    print(f"\n=== check run {run_number}")
    print(f"off topic caught      {scores['off_topic_caught']}/{scores['off_topic_questions']}  missed: {scores['missed_off_topic']}")
    print(f"near misses through   {scores['near_misses_let_through']}/{scores['near_misses']}  blocked: {scores['blocked_near_misses']}")
    print(f"rules wrongly blocked {len(scores['rules_questions_blocked'])}/{scores['rules_questions']}  {scores['rules_questions_blocked']}")
    print(f"off-topic probes      {scores['off_topic_probes_caught']}/{scores['off_topic_probes']}")
    print(f"failed open           {len(scores['failed_open'])}  {scores['failed_open']}")
    print(f"latency p50 {scores['p50_seconds']} s · p95 {scores['p95_seconds']} s · cost ${scores['cost_dollars']:.4f}", flush=True)


# ===== Part B: full answers =====

# Answers one refusal question with the real bot and returns its refusal and cost
def answer_one_question(question: dict, rules_bot: RulesBot, recording_client: RecordingClient,
                        cost_tracker: CostTracker) -> dict:
    if cost_tracker.is_over_cap():
        raise CostCapReached(f"spent ${cost_tracker.spent_dollars:.2f}, over the ${COST_CAP_DOLLARS:.2f} cap")
    started = time.perf_counter()
    error_text = None
    try:
        rules_answer = rules_bot.answer(question["question"])
        refused, refusal_kind, answer_text = rules_answer.refused, rules_answer.refusal_kind, rules_answer.answer
    except Exception as error:
        refused, refusal_kind, answer_text = None, None, ""
        error_text = f"{type(error).__name__}: {error}"
    seconds = time.perf_counter() - started
    cost = cost_of_calls(recording_client.take_calls())
    cost_tracker.add(cost)
    return {"id": question["id"], "set": question["set"], "refused": refused, "refusal_kind": refusal_kind,
            "answer": answer_text, "seconds": round(seconds, 1), "cost": cost, "error": error_text}


# Answers every refusal question with the real bot, RUN_COUNT times, and logs and prints each run
def run_answer_part(recording_client: RecordingClient, settings, cost_tracker: CostTracker,
                    questions_at_once: int) -> list[list[dict]]:
    questions = load_refusal_questions()
    chunks = load_chunks()
    live_search = build_live_vector_search(chunks, recording_client, settings.mistral_embedding_model)
    topic_check = build_mistral_topic_check(recording_client, settings.mistral_draft_model)
    rules_bot = RulesBot(recording_client, settings, chunks, load_rule_map(), live_search.search,
                         is_rules_question=topic_check)
    all_runs = []
    for run_number in range(1, RUN_COUNT + 1):
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=questions_at_once) as executor:
            rows = list(executor.map(lambda question: answer_one_question(question, rules_bot, recording_client,
                                                                          cost_tracker), questions))
        kinds = Counter(str(row["refusal_kind"]) for row in rows)
        scores = {"not_covered": kinds["not_covered"], "off_topic": kinds["off_topic"],
                  "answered": sum(row["refused"] is False for row in rows),
                  "errors": sorted(f"{row['id']} ({row['error']})" for row in rows if row["error"] is not None),
                  "questions": len(rows), "cost_dollars": round(sum(row["cost"] for row in rows), 4),
                  "rows": [{key: row[key] for key in ("id", "set", "refused", "refusal_kind", "seconds", "error")}
                           for row in rows]}
        run_settings = {"run": f"{datetime.now(timezone.utc):%Y%m%dT%H%M}-topic-check-answers-run{run_number}",
                        "part": "answers",
                        "check_model": settings.mistral_draft_model, "answer_model": settings.mistral_answer_model,
                        "reasoning_effort": settings.mistral_reasoning_effort, "flow": "gather-then-write",
                        "setup": "hybrid", "questions": len(questions), "held_out_left_out": True,
                        "questions_at_once": questions_at_once}
        run_settings.update(read_code_version())
        append_run(MEASUREMENT_STAGE, run_settings, scores, round(time.perf_counter() - started, 2))
        print(f"\n=== answer run {run_number}: not_covered {scores['not_covered']} · off_topic {scores['off_topic']}"
              f" · answered {scores['answered']} · errors {len(scores['errors'])} of {len(rows)}"
              f" · cost ${scores['cost_dollars']:.3f}", flush=True)
        for row in rows:
            print(f"  {row['id']:<28} refused={row['refused']} kind={row['refusal_kind']} {row['seconds']} s")
        all_runs.append(rows)
    return all_runs


# Prints the questions whose refusal or refusal kind differs across the runs
def print_changes_across_runs(all_runs: list[list[dict]]) -> None:
    print("\n=== answers that change across the runs")
    outcomes_by_id = {}
    for rows in all_runs:
        for row in rows:
            outcomes_by_id.setdefault(row["id"], []).append(f"{row['refused']}/{row['refusal_kind']}")
    changed = {question_id: outcomes for question_id, outcomes in outcomes_by_id.items() if len(set(outcomes)) > 1}
    print(changed or "none", flush=True)


# ===== Entry point =====

# Runs the parts the command line names, under one cost cap
def main() -> None:
    parser = argparse.ArgumentParser(description="Measure the slice 7 topic check with paid calls.")
    parser.add_argument("--part", choices=["check", "answers", "both"], default="both")
    parser.add_argument("--parallel", type=int, default=QUESTIONS_AT_ONCE, help="questions at once")
    arguments = parser.parse_args()

    settings = load_settings()
    recording_client = RecordingClient(build_mistral_client(settings))
    cost_tracker = CostTracker(COST_CAP_DOLLARS)
    if arguments.part in ("check", "both"):
        run_check_part(recording_client, settings, cost_tracker, arguments.parallel)
        print(f"\npart A done: ${cost_tracker.spent_dollars:.4f} so far", flush=True)
    if arguments.part in ("answers", "both"):
        all_runs = run_answer_part(recording_client, settings, cost_tracker, arguments.parallel)
        print_changes_across_runs(all_runs)
    print(f"\ntotal cost ${cost_tracker.spent_dollars:.3f}", flush=True)


if __name__ == "__main__":
    main()
