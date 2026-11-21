"""
Counts how many tool turns the product flow takes with the rule map and without it, with no judge
(Job, 21 Nov 2026: "with map and no map, how many tool turns").

The rule map is data/rule_links.json: the links between clauses (cites, overrides, para exceptions, instructions for
officials, diagrams). "No map" swaps in an empty map, in the starting sources and in the tools alike. Everything else
stays the same: gather-then-write, the hybrid setup, top 5, list items (those come from the clause structure, not the
map), temperature 0 and the 41 Phase 2 questions. The arms take turns, 3 runs each. On 21 Nov it was stopped after
the first pair to save credit, so runs.jsonl holds one run per arm (a preview, not a win).
Code counts tool turns, model calls, refusals, format errors, cost and time from each reply; nothing is judged.

  Input:  evals/phase2_questions.json; data/ (the chunks, their saved vectors and the rule map); MISTRAL_API_KEY
  Output: one line per run in evals/runs.jsonl (stage "tool-turns-map"), and a printed table

Run from the project root:
    uv run python -m experiments.count_tool_turns_with_and_without_map
"""

import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from answer_flows.gather_then_write.gather_and_write_rules import GATHER_RULES
from answer_flows.gather_then_write.gather_then_write import gather_then_write
from answer_flows.shared.mistral_client import build_mistral_client
from answer_flows.shared.rule_tools import RuleTools
from evals.log_eval_run import append_run
from evals.probes import load_phase2_questions
from experiments.run_answer_experiment import read_code_version
from experiments.run_topic_check_eval import CostTracker, RecordingClient, cost_of_calls
from retrieval.expand_with_rule_links import index_links, load_rule_map
from retrieval.load_rule_chunks import load_chunks
from retrieval.retrieve_sources import DEFAULT_TOP_K, build_live_vector_search, build_retrieve_function
from settings import load_settings


# Constants
## How many runs per arm, questions answered at once, the cost at which the command stops (Job approved about $3.50)
RUNS_PER_ARM = 3
QUESTIONS_AT_ONCE = 4
COST_CAP_DOLLARS = 6.00
## The stage runs.jsonl records
MEASUREMENT_STAGE = "tool-turns-map"


# Answers one question the way RulesBot.answer does after the topic check, and records what code can count
def answer_one_question(question: dict, chunks: list[dict], search_function, rule_map: dict, settings,
                        recording_client: RecordingClient, cost_tracker: CostTracker) -> dict:
    started = time.perf_counter()
    chunk_by_id = {chunk["id"]: chunk for chunk in chunks}
    retrieve = build_retrieve_function(search_function, DEFAULT_TOP_K, chunk_by_id, rule_map)
    rule_tools = RuleTools(chunks, search_function, rule_map)
    # One failed question is recorded by name and the run goes on: no other question depends on it
    try:
        reply = gather_then_write(recording_client, settings.mistral_answer_model, settings.mistral_reasoning_effort,
                                  GATHER_RULES, question["question"], retrieve(question["question"]), rule_tools)
    except Exception as error:
        cost_tracker.add(cost_of_calls(recording_client.take_calls()))
        return {"id": question["id"], "tool_rounds": None, "model_calls": None, "refused": None,
                "is_format_error": True, "error": f"{type(error).__name__}: {error}", "cost": 0.0,
                "seconds": round(time.perf_counter() - started, 1)}
    cost = cost_of_calls(recording_client.take_calls())
    cost_tracker.add(cost)
    refused = reply.answer.refused if reply.answer is not None else None
    return {"id": question["id"], "tool_rounds": reply.tool_rounds, "model_calls": reply.model_calls,
            "refused": refused, "is_format_error": reply.is_format_error, "error": reply.error_message,
            "cost": cost, "seconds": round(time.perf_counter() - started, 1)}


# Answers every question once in one arm, and logs the run
def run_one_arm(arm_name: str, rule_map: dict, run_number: int, questions: list[dict], chunks: list[dict],
                search_function, settings, recording_client: RecordingClient, cost_tracker: CostTracker) -> dict:
    if cost_tracker.is_over_cap():
        raise RuntimeError(f"stopped: spent ${cost_tracker.spent_dollars:.2f}, over the ${COST_CAP_DOLLARS:.2f} cap")
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=QUESTIONS_AT_ONCE) as executor:
        rows = list(executor.map(lambda question: answer_one_question(question, chunks, search_function, rule_map,
                                                                      settings, recording_client, cost_tracker),
                                 questions))

    # Tool turns are counted on every question that ran; refusals and failures are listed by name
    finished_rows = [row for row in rows if row["tool_rounds"] is not None]
    tool_rounds = [row["tool_rounds"] for row in finished_rows]
    scores = {"mean_tool_rounds": round(statistics.mean(tool_rounds), 3),
              "questions_with_no_tool_round": sum(rounds == 0 for rounds in tool_rounds),
              "most_tool_rounds": max(tool_rounds),
              "mean_model_calls": round(statistics.mean(row["model_calls"] for row in finished_rows), 3),
              "failed": sorted(f"{row['id']} ({row['error']})" for row in rows if row["tool_rounds"] is None),
              "refused": sorted(row["id"] for row in rows if row["refused"] is True),
              "format_errors": sorted(row["id"] for row in rows if row["is_format_error"]),
              "cost_per_question": round(sum(row["cost"] for row in rows) / len(rows), 5),
              "median_seconds": statistics.median(row["seconds"] for row in rows),
              "questions": len(rows),
              "rows": rows}
    run_settings = {"run": f"{datetime.now(timezone.utc):%Y%m%dT%H%M}-tool-turns-{arm_name}-run{run_number}",
                    "rule_map": arm_name, "flow": "gather-then-write", "setup": "hybrid", "top_k": DEFAULT_TOP_K,
                    "answer_model": settings.mistral_answer_model,
                    "reasoning_effort": settings.mistral_reasoning_effort, "questions_at_once": QUESTIONS_AT_ONCE}
    run_settings.update(read_code_version())
    append_run(MEASUREMENT_STAGE, run_settings, scores, round(time.perf_counter() - started, 2))
    print(f"{arm_name:7} run {run_number}: tool turns {scores['mean_tool_rounds']:.2f}  "
          f"no-tool {scores['questions_with_no_tool_round']}  refused {len(scores['refused'])}  "
          f"format errors {len(scores['format_errors'])}  ${scores['cost_per_question']:.4f}/q  "
          f"median {scores['median_seconds']} s", flush=True)
    return scores


def main() -> None:
    # Load what both arms share; the only difference between them is the rule map
    settings = load_settings()
    recording_client = RecordingClient(build_mistral_client(settings))
    cost_tracker = CostTracker(COST_CAP_DOLLARS)
    chunks = load_chunks()
    search_function = build_live_vector_search(chunks, recording_client, settings.mistral_embedding_model).search
    questions = load_phase2_questions()
    map_by_arm = {"map": load_rule_map(), "no-map": index_links([])}

    # The arms take turns, so a slow or busy hour hits both alike
    scores_by_arm = {arm_name: [] for arm_name in map_by_arm}
    for run_number in range(1, RUNS_PER_ARM + 1):
        for arm_name, rule_map in map_by_arm.items():
            scores = run_one_arm(arm_name, rule_map, run_number, questions, chunks, search_function, settings,
                                 recording_client, cost_tracker)
            scores_by_arm[arm_name].append(scores)

    # Print each arm's range across its runs
    for arm_name, runs in scores_by_arm.items():
        means = [scores["mean_tool_rounds"] for scores in runs]
        print(f"{arm_name:7} tool turns per question: {means}, average {statistics.mean(means):.2f}")
    print(f"total cost ${cost_tracker.spent_dollars:.2f}", flush=True)


if __name__ == "__main__":
    main()
