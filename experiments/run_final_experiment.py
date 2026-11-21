"""
The final experiment (Job, 21 Nov 2026): one locked question set, three flows, code checks only, no judge.

  plain-agent    the "before": the question alone, then the search and read tools (record 0021's setup B,
                 loop-call-with-tools); no topic screen, no starting sources
  design         the product route: the topic screen, then vector top 5 + rule links, then gather-then-write
                 with the code gate and code-copied quotes (as RulesBot.answer)
  design-no-map  the same, with an empty rule map in the starting sources and in the tools

The questions are evals/final_experiment_questions.json, locked before any run: every run records the file's
SHA-256, so a changed set can't pass unnoticed. Code checks each answer (the refusal outcome, the quotes, the cited
clause) and records tool turns, model calls, cost from each call's tokens and the time. The judge's lines (claim
matches its source, correct) are left for a later re-grade of the saved answers.

  Input:  evals/final_experiment_questions.json; data/ (the chunks, their saved vectors and the rule map); MISTRAL_API_KEY
  Output: evals/answer_runs/<run>-answers.jsonl, one line in evals/runs.jsonl (stage "final-experiment"), printed scores

Run from the project root:
    uv run python -m experiments.run_final_experiment --flow design --dry-run    # one question per category, not logged
    uv run python -m experiments.run_final_experiment --flow design --run-number 1
"""

import argparse
import hashlib
import json
import statistics
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from answer_flows.gather_then_write.gather_and_write_rules import GATHER_RULES
from answer_flows.gather_then_write.gather_then_write import gather_then_write
from answer_flows.shared.flow_reply import FlowReply
from answer_flows.shared.mistral_client import build_mistral_client
from answer_flows.shared.rule_tools import RuleTools
from answer_flows.topic_screen import build_mistral_topic_check, build_off_topic_answer
from evals.answer_run_files import ANSWER_RUNS_FOLDER, append_line
from evals.checks.check_citations import find_citation_problems
from evals.checks.check_refusals import CORRECT_REFUSAL, FALSE_REFUSAL, MISSED_REFUSAL, refusal_outcome
from evals.code_checks import find_code_failures
from evals.log_eval_run import append_run
from experiments.retired_flows.loop_call_with_tools.answer_with_tools import answer_with_tools
from experiments.retired_flows.single_call.answer_rules import build_answer_rules
from experiments.run_answer_experiment import build_answer_line, read_code_version
from experiments.run_topic_check_eval import RecordingClient, cost_of_calls
from retrieval.expand_with_rule_links import index_links, load_rule_map
from retrieval.load_rule_chunks import PROJECT_FOLDER, load_chunks
from retrieval.retrieve_sources import DEFAULT_TOP_K, build_live_vector_search, build_retrieve_function
from settings import Settings, load_settings


# Constants
## Path to the locked question set
QUESTIONS_FILE = PROJECT_FOLDER / "evals" / "final_experiment_questions.json"
## The flows, the stage runs.jsonl records, and how many questions are answered at once
FLOW_NAMES = ("plain-agent", "design", "design-no-map")
MEASUREMENT_STAGE = "final-experiment"
QUESTIONS_AT_ONCE = 4
## The code failure that means the answer cites none of the clauses that hold the answer
WRONG_CLAUSE_PREFIX = "wrong clause"


# ===== The locked questions =====

def load_locked_questions() -> tuple[list[dict], str]:
    """Returns the questions and the file's SHA-256, so each run records exactly which set it answered."""
    file_bytes = QUESTIONS_FILE.read_bytes()
    return json.loads(file_bytes)["questions"], hashlib.sha256(file_bytes).hexdigest()


def pick_one_per_category(questions: list[dict]) -> list[dict]:
    """Returns the first question of each category, for a dry run that meets every path once."""
    picked_by_category = {}
    for question in questions:
        picked_by_category.setdefault(question["category"], question)
    return list(picked_by_category.values())


# ===== The three flows =====

def build_flow_function(flow_name: str, chunks: list[dict], recording_client: RecordingClient,
                        settings: Settings) -> Callable[[str], FlowReply]:
    """Returns a function that answers one question with the named flow and returns its reply."""
    search_function = build_live_vector_search(chunks, recording_client, settings.mistral_embedding_model).search
    chunk_by_id = {chunk["id"]: chunk for chunk in chunks}

    # The plain agent: the question alone, the tools, and the answer prompt with its search steps
    if flow_name == "plain-agent":
        rule_map = load_rule_map()
        agent_rules = build_answer_rules([], uses_tools=True)

        def answer_with_plain_agent(question_text: str) -> FlowReply:
            """Answers with the tools only; each question gets fresh tools, which remember what it has seen."""
            rule_tools = RuleTools(chunks, search_function, rule_map)
            return answer_with_tools(recording_client, settings.mistral_answer_model,
                                     settings.mistral_reasoning_effort, agent_rules, question_text, [], rule_tools)
        return answer_with_plain_agent

    # The design, with the rule map or with an empty one. This repeats RulesBot.answer's steps (topic screen, retrieve,
    # gather-then-write) instead of calling it, because RulesBot.answer returns only the answer, not the tool rounds
    # and model calls this test counts; keep the two in step
    rule_map = load_rule_map()
    if flow_name == "design-no-map":
        rule_map = index_links([])
    retrieve = build_retrieve_function(search_function, DEFAULT_TOP_K, chunk_by_id, rule_map)
    is_rules_question = build_mistral_topic_check(recording_client, settings.mistral_draft_model)

    def answer_with_design(question_text: str) -> FlowReply:
        """Answers with the topic screen, then the starting sources and gather-then-write."""
        # As in RulesBot.passes_topic_check: a screen that fails lets the question through
        try:
            passes_screen = is_rules_question(question_text)
        except Exception:
            passes_screen = True
        if not passes_screen:
            return FlowReply(answer=build_off_topic_answer(), is_format_error=False, error_message=None,
                             raw_reply="", thinking="", shown_chunks=[])
        rule_tools = RuleTools(chunks, search_function, rule_map)
        return gather_then_write(recording_client, settings.mistral_answer_model, settings.mistral_reasoning_effort,
                                 GATHER_RULES, question_text, retrieve(question_text), rule_tools)
    return answer_with_design


# ===== One question =====

def answer_and_check(question: dict, answer_one_question: Callable[[str], FlowReply], chunks: list[dict],
                     recording_client: RecordingClient, settings: Settings) -> dict:
    """Answers one question, runs the code checks, and returns its answer line with cost and time."""
    started = time.perf_counter()

    # A failed call is recorded by name and the run goes on: no other question depends on it
    try:
        reply = answer_one_question(question["question"])
    except Exception as error:
        reply = FlowReply(answer=None, is_format_error=True, error_message=f"{type(error).__name__}: {error}",
                          raw_reply="", thinking="", shown_chunks=[])
    seconds = time.perf_counter() - started

    # The answer line in the usual run-file shape, with the cost of every call this question made (topic screen too)
    answer_line = build_answer_line(question, reply, settings.mistral_answer_model)
    answer_line["answer_cost"] = cost_of_calls(recording_client.take_calls())
    answer_line["answer_seconds"] = round(seconds, 1)
    answer_line["link_relation"] = question.get("link_relation")

    # The code checks: the refusal outcome, the quotes and the cited clause
    if not reply.is_format_error:
        answer_line["answer"] = reply.answer.model_dump()
        answer_line["citation_problems"] = find_citation_problems(reply.answer, reply.shown_chunks)
        answer_line["refusal_outcome"] = refusal_outcome(question, reply.answer.refused)
        chunk_by_id = {chunk["id"]: chunk for chunk in chunks}
        answer_line["code_failures"], answer_line["code_warnings"] = find_code_failures(answer_line, question, chunks,
                                                                                         chunk_by_id)
    else:
        answer_line["raw_reply"] = reply.raw_reply
    return answer_line


# ===== Scoring a run =====

def has_wrong_clause(answer_line: dict) -> bool:
    """True when the answer cites none of the clauses that hold the answer."""
    return any(failure.startswith(WRONG_CLAUSE_PREFIX) for failure in answer_line["code_failures"])


def ids_with_outcome(answer_lines: list[dict], outcome: str) -> list[str]:
    """Returns the ids of the questions with the given refusal outcome, sorted."""
    return sorted(line["id"] for line in answer_lines if line["refusal_outcome"] == outcome)


def score_run(answer_lines: list[dict]) -> dict:
    """Returns what code can count: refusals right and wrong, cited clauses, quotes, tool turns, cost and time."""
    should_refuse_lines = [line for line in answer_lines if line["should_refuse"]]
    linked_lines = [line for line in answer_lines if not line["should_refuse"]]
    answered_linked_lines = [line for line in linked_lines if line["refusal_outcome"] == "answered"]
    # A failed question has no tool rounds or cost to count, so the means leave it out (its id is in format_errors)
    finished_lines = [line for line in answer_lines if not line["is_format_error"]]
    finished_linked_lines = [line for line in linked_lines if not line["is_format_error"]]
    return {
        "should_refuse": len(should_refuse_lines),
        "correct_refusals": len(ids_with_outcome(answer_lines, CORRECT_REFUSAL)),
        "missed_refusals": ids_with_outcome(answer_lines, MISSED_REFUSAL),
        "linked_questions": len(linked_lines),
        "false_refusals": ids_with_outcome(answer_lines, FALSE_REFUSAL),
        "cites_right_clause": sum(not has_wrong_clause(line) for line in answered_linked_lines),
        "answered_linked": len(answered_linked_lines),
        "answers_with_citation_problems": sorted(line["id"] for line in finished_lines if line["citation_problems"]),
        "format_errors": sorted(f"{line['id']} ({line['error_message']})" for line in answer_lines
                                if line["is_format_error"]),
        "mean_tool_rounds": round(statistics.mean(line["tool_rounds"] for line in finished_lines), 3),
        "mean_tool_rounds_linked": round(statistics.mean(line["tool_rounds"] for line in finished_linked_lines), 3),
        "mean_model_calls": round(statistics.mean(line["model_calls"] for line in finished_lines), 3),
        "cost_per_question": round(statistics.mean(line["answer_cost"] for line in answer_lines), 5),
        "cost_per_linked_answer": round(statistics.mean(line["answer_cost"] for line in linked_lines), 5),
        "total_cost": round(sum(line["answer_cost"] for line in answer_lines), 4),
        "median_seconds": statistics.median(line["answer_seconds"] for line in answer_lines),
        "questions": len(answer_lines),
    }


# ===== One run =====

def parse_arguments() -> argparse.Namespace:
    """Returns the flow, the run number and whether this is a dry run."""
    parser = argparse.ArgumentParser(description="Answer the locked question set with one flow; code checks only.")
    parser.add_argument("--flow", required=True, choices=FLOW_NAMES)
    parser.add_argument("--run-number", type=int, default=1, help="which of the flow's runs this is (default 1)")
    parser.add_argument("--dry-run", action="store_true", help="one question per category, and don't log the run")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    settings = load_settings()
    recording_client = RecordingClient(build_mistral_client(settings))
    chunks = load_chunks()
    questions, questions_sha256 = load_locked_questions()
    if arguments.dry_run:
        questions = pick_one_per_category(questions)
    answer_one_question = build_flow_function(arguments.flow, chunks, recording_client, settings)

    # Name the run, then answer QUESTIONS_AT_ONCE questions at a time, saving each line as it finishes
    label = f"final-{arguments.flow}-run{arguments.run_number}"
    if arguments.dry_run:
        label = f"{label}-dry-run"
    run_name = f"{datetime.now(timezone.utc):%Y%m%dT%H%M}-{label}"
    answers_path = Path(ANSWER_RUNS_FOLDER) / f"{run_name}-answers.jsonl"
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=QUESTIONS_AT_ONCE) as executor:
        answer_lines = list(executor.map(
            lambda question: answer_and_check(question, answer_one_question, chunks, recording_client, settings),
            questions))
    for answer_line in answer_lines:
        append_line(answers_path, answer_line)
    seconds = time.perf_counter() - started

    # Score and print, then log only a real run
    scores = score_run(answer_lines)
    print(json.dumps(scores, indent=2), flush=True)
    print(f"saved {answers_path.name} in evals/answer_runs/")
    if arguments.dry_run:
        print("dry run: not logged to evals/runs.jsonl")
        return
    run_settings = {"run": run_name, "flow": arguments.flow, "run_number": arguments.run_number,
                    "questions_file_sha256": questions_sha256, "answer_model": settings.mistral_answer_model,
                    "check_model": settings.mistral_draft_model, "reasoning_effort": settings.mistral_reasoning_effort,
                    "top_k": DEFAULT_TOP_K, "judge": "none (code checks only)",
                    "questions_at_once": QUESTIONS_AT_ONCE}
    run_settings.update(read_code_version())
    append_run(MEASUREMENT_STAGE, run_settings, scores, seconds)


if __name__ == "__main__":
    main()
