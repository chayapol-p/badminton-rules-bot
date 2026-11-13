"""
Answers the questions with an agent setup (Stage 3), checks and grades every answer the same way as Stage 2, prints the scores and logs the run.

Two setups, picked with --setup:
  agentic  setup B: the model starts with the question only, and finds every source with the tools
  hybrid   setup C: the model starts with setup A's sources (vector top 5, the rule links and a list
           heading's items, exactly as experiments/compare_answer_setups.py retrieves), plus the tools
Setup A is experiments/compare_answer_setups.py itself.

Fixed for both (experiment rule 1): the answer rules, the answer model at temperature 0, the RulesAnswer
shape, the code checks and the judge, all as in Stage 2. Only where the sources come from changes.

The tools' searches embed the model's own queries live with mistral-embed (a tiny cost, not counted);
the questions themselves use their saved vectors.

  --setup     agentic | hybrid
  --agent-rule  an extra agent rule to test, by name (answer_flows/shared/tool_loop.py EXTRA_AGENT_RULES). With none
              named, the run uses DEFAULT_AGENT_RULE_NAMES (record 0022)
  --no-agent-rules  run with no extra agent rules, as the runs before record 0022 did
  --flow      one-call (slice 4, the default): one tool loop picks sentences and writes the answer
              gather-write (slice 5): the tool loop only picks sentences, code refuses when no part has one,
              and a write call with no tools answers (answer_flows/gather_then_write/gather_then_write.py)
  --unseen    answer the unseen questions instead of dev and the probes (once per setup)
  --label     a short name for the run (default: the setup name)
  --dry-run   answer only the first question, and don't log the run

Writes the same two files per run as Stage 2 (evals/answer_runs/<time>-<label>-answers.jsonl and
-grades.jsonl); each answer line also holds its tool calls, tool rounds and model calls.

Run from the project root:
    uv run python -m experiments.compare_agent_setups --setup hybrid --unseen --dry-run
    uv run python -m experiments.compare_agent_setups --setup hybrid --unseen
    uv run python -m experiments.compare_agent_setups --setup hybrid --flow gather-write --dry-run
"""

import argparse
import json
import time
from collections.abc import Callable
from datetime import datetime, timezone
from statistics import mean

import numpy
from anthropic import Anthropic
from mistralai.client import Mistral

from answer_flows.one_call_with_tools.answer_with_tools import answer_with_tools
from answer_flows.shared.tool_loop import DEFAULT_AGENT_RULE_NAMES, EXTRA_AGENT_RULES, AgentReply
from answer_flows.gather_then_write.gather_then_write import gather_then_write
from answer_flows.shared.rule_tools import RuleTools
from answer_flows.gather_then_write.gather_and_write_rules import GATHER_RULES
from answer_flows.single_call.answer_rules import build_answer_rules
from evals.checks.check_refusals import should_refuse
from answer_flows.shared.read_model_reply import MAX_ANSWER_TOKENS
from app.settings import load_settings
from evals.answer_run_files import ANSWER_RUNS_FOLDER, append_line
from evals.golden_answer_chunks import load_chunks, load_questions
from evals.log_eval_run import append_run
from evals.probes import load_probes, load_unseen_questions
from evals.token_costs import call_cost
from experiments.compare_answer_setups import (DEFAULT_TOP_K, MISTRAL_RETRY, SECONDS_BETWEEN_QUESTIONS,
                                               build_clause_vector_search, build_retrieve_function, check_and_grade,
                                               print_scores, summarise_answer_run)
from retrieval.expand_with_rule_links import load_rule_map
from retrieval.stored_embeddings import load_embeddings
from retrieval.vector_search import VectorSearch


# Constants
## The two agent setups, by their --setup name
SETUP_NAMES = ["agentic", "hybrid"]

## The two answer flows, by their --flow name: the function that answers one question, and its rules
ANSWER_FUNCTION_BY_FLOW = {"one-call": answer_with_tools, "gather-write": gather_then_write}
DEFAULT_FLOW = "one-call"


# ===== The tools' search: live query vectors =====

def build_live_vector_search(chunks: list[dict], mistral_client: Mistral, model: str) -> VectorSearch:
    """Returns vector search over the clauses' saved vectors, embedding each new query with one live API call."""
    chunk_vector_by_id = load_embeddings("clauses_search_text", model)
    chunk_vectors = numpy.array([chunk_vector_by_id[chunk["id"]] for chunk in chunks])
    vector_by_query = {}

    def embed_query(query_text: str) -> list[float]:
        """Returns the query's vector, calling the API only the first time a query is seen."""
        if query_text not in vector_by_query:
            response = mistral_client.embeddings.create(model=model, inputs=[query_text])
            vector_by_query[query_text] = response.data[0].embedding
        return vector_by_query[query_text]

    return VectorSearch(chunks, chunk_vectors, embedding_function=embed_query)


# ===== One question =====

def build_answer_line(question: dict, reply: AgentReply, answer_model: str) -> dict:
    """Returns the answer line in the Stage 2 shape, plus the agent's tool calls, rounds and model calls."""
    return {
        "id": question["id"],
        "split": question["split"],
        "category": question["category"],
        "needs": question.get("needs"),
        "question": question["question"],
        "should_refuse": should_refuse(question),
        "retrieved_ids": [chunk["id"] for chunk in reply.shown_chunks],
        "words_returned": sum(len(chunk["text"].split()) for chunk in reply.shown_chunks),
        "answer": None,
        "is_format_error": reply.is_format_error,
        "error_message": reply.error_message,
        "thinking": reply.thinking,
        "citation_problems": [],
        "refusal_outcome": None,
        "code_failures": ["format error"],
        "code_warnings": [],
        "tool_rounds": reply.tool_rounds,
        "tool_calls": reply.tool_calls,
        "tools_turned_off": reply.tools_turned_off,
        "model_calls": reply.model_calls,
        "bad_picks": reply.bad_picks,
        "write_called": reply.write_called,
        "answer_cost": call_cost(answer_model, reply.input_tokens, reply.output_tokens),
        "judge_cost": 0.0,
    }


def answer_and_grade_with_tools(question: dict, starting_retrieve: Callable[[str], list[dict]] | None,
                                rule_tools: RuleTools, answer_rules: str, chunks: list[dict],
                                chunk_by_id: dict[str, dict], mistral_client: Mistral, answer_model: str,
                                reasoning_effort: str, anthropic_client: Anthropic, judge_model: str,
                                extra_agent_rule_names: list[str], flow: str = DEFAULT_FLOW) -> tuple[dict, dict]:
    """Returns one question's answer line and grade line, answered with the tools and graded as in Stage 2."""

    # Setup C starts from setup A's bundle; setup B starts from none
    starting_items = []
    if starting_retrieve is not None:
        starting_items = starting_retrieve(question["question"])
    answer_function = ANSWER_FUNCTION_BY_FLOW[flow]
    reply = answer_function(mistral_client, answer_model, reasoning_effort, answer_rules, question["question"],
                            starting_items, rule_tools, extra_agent_rule_names)
    answer_line = build_answer_line(question, reply, answer_model)

    # A reply that didn't fit the shape can't be checked or graded: it counts as a fail
    if reply.is_format_error:
        answer_line["raw_reply"] = reply.raw_reply
        return answer_line, {"id": question["id"], "passed": False, "judged": False, "grade": None}

    # The same code checks and judge as Stage 2, over every chunk the model saw
    answer_line["answer"] = reply.answer.model_dump()
    grade_line = check_and_grade(answer_line, reply.answer, question, reply.shown_chunks, chunks, chunk_by_id,
                                 anthropic_client, judge_model)
    return answer_line, grade_line


# ===== The agent's own numbers =====

def requested_top_k(tool_call: dict) -> object:
    """Returns the top_k a search_rules call asked for, as the model sent it (None when it sent none or bad JSON)."""
    arguments = tool_call["arguments"]
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return None
    return arguments.get("top_k")


def summarise_tool_use(answer_lines: list[dict]) -> dict:
    """Returns how the agent used its tools: rounds, calls, errors, questions that reached the limit and the top_k it asked for."""

    # Every tool call in the run, and the top_k of each search
    tool_calls = []
    for line in answer_lines:
        tool_calls.extend(line["tool_calls"])
    requested_top_ks = []
    for tool_call in tool_calls:
        if tool_call["tool"] == "search_rules":
            requested_top_ks.append(requested_top_k(tool_call))
    rounds = [line["tool_rounds"] for line in answer_lines]
    return {
        "mean_tool_rounds": round(mean(rounds), 2),
        "most_tool_rounds": max(rounds),
        "questions_with_no_tool_call": sum(1 for round_count in rounds if round_count == 0),
        "tool_calls": len(tool_calls),
        "tool_errors": sum(1 for call in tool_calls if call["error"]),
        "questions_at_limit": sum(1 for line in answer_lines if line["tools_turned_off"]),
        "mean_model_calls": round(mean(line["model_calls"] for line in answer_lines), 2),
        "bad_picks": sum(len(line["bad_picks"]) for line in answer_lines),
        "questions_with_a_bad_pick": sum(1 for line in answer_lines if line["bad_picks"]),
        "write_calls": sum(1 for line in answer_lines if line["write_called"]),
        "requested_top_ks": requested_top_ks,
    }


def print_tool_use(tool_use: dict) -> None:
    """Prints the agent's tool use, under the Stage 2 scores."""
    print(f"tool rounds  mean {tool_use['mean_tool_rounds']}  · most {tool_use['most_tool_rounds']}  "
          f"· no tool call on {tool_use['questions_with_no_tool_call']} questions  · model calls mean {tool_use['mean_model_calls']}")
    print(f"tool calls {tool_use['tool_calls']}  · errors {tool_use['tool_errors']}  "
          f"· questions that reached the round limit {tool_use['questions_at_limit']}")
    print(f"top_k asked for: {tool_use['requested_top_ks']}")
    print(f"bad picks {tool_use['bad_picks']} on {tool_use['questions_with_a_bad_pick']} questions  "
          f"· write calls {tool_use['write_calls']}")


# ===== Running one setup =====

def run_agent_setup(setup_name: str, label: str, is_dry_run: bool, uses_unseen: bool,
                    extra_agent_rule_names: list[str], flow: str = DEFAULT_FLOW) -> dict:
    """Answers, checks and grades every question with one agent setup, then prints, saves and logs the run."""
    settings = load_settings()
    chunks = load_chunks()
    chunk_by_id = {chunk["id"]: chunk for chunk in chunks}
    rule_map = load_rule_map()

    # The questions: dev and the probes, or the unseen set
    questions = load_questions("dev") + load_probes()
    split_name = "dev+probes"
    if uses_unseen:
        questions = load_unseen_questions()
        split_name = "unseen"
    if is_dry_run:
        questions = questions[:1]

    # The clients, and the tools over a live-query search
    mistral_client = Mistral(api_key=settings.mistral_api_key.get_secret_value(), retry_config=MISTRAL_RETRY)
    anthropic_client = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    live_search = build_live_vector_search(chunks, mistral_client, settings.mistral_embedding_model)
    rule_tools = RuleTools(chunks, live_search.search, rule_map)

    # Setup C's starting sources come from setup A's own retrieve step; setup B has none
    starting_retrieve = None
    if setup_name == "hybrid":
        question_search = build_clause_vector_search(chunks, questions, settings.mistral_embedding_model).search
        starting_retrieve = build_retrieve_function(question_search, DEFAULT_TOP_K, chunk_by_id, rule_map)
    answer_rules = build_answer_rules([])
    if flow == "gather-write":
        answer_rules = GATHER_RULES

    # Name the run first, so each answer can be saved the moment it's done
    run_name = f"{datetime.now(timezone.utc):%Y%m%dT%H%M}-{label}"
    ANSWER_RUNS_FOLDER.mkdir(parents=True, exist_ok=True)
    answers_path = ANSWER_RUNS_FOLDER / f"{run_name}-answers.jsonl"
    grades_path = ANSWER_RUNS_FOLDER / f"{run_name}-grades.jsonl"

    # Answer and grade each question, saving both lines before the next, so a crash keeps what was paid for
    started = time.perf_counter()
    answer_lines = []
    grade_lines = []
    for question_number, question in enumerate(questions, start=1):
        print(f"{question_number}/{len(questions)} {question['id']}", flush=True)
        answer_line, grade_line = answer_and_grade_with_tools(question, starting_retrieve, rule_tools, answer_rules,
                                                              chunks, chunk_by_id, mistral_client,
                                                              settings.mistral_answer_model,
                                                              settings.mistral_reasoning_effort, anthropic_client,
                                                              settings.claude_judge_model, extra_agent_rule_names,
                                                              flow)
        append_line(answers_path, answer_line)
        append_line(grades_path, grade_line)
        answer_lines.append(answer_line)
        grade_lines.append(grade_line)
        time.sleep(SECONDS_BETWEEN_QUESTIONS)
    seconds = time.perf_counter() - started

    # Score with the Stage 2 scorer, add the tool use, print, and log only a finished, real run
    passed_by_id = {line["id"]: line["passed"] for line in grade_lines}
    scores = summarise_answer_run(answer_lines, passed_by_id)
    scores["tool_use"] = summarise_tool_use(answer_lines)
    print_scores(scores, answer_lines, passed_by_id)
    print_tool_use(scores["tool_use"])
    # Slice 4 refuses inside the one answer; slice 5 refuses at the gate, before the write call
    refusal_setting = "code, from the parts"
    if flow == "gather-write":
        refusal_setting = "code gate before the write call"
    run_settings = {
        "run": run_name,
        "setup": setup_name,
        "search": "vector",
        "chunks": "clauses",
        "field": "search_text",
        "split": split_name,
        "starting_sources": setup_name == "hybrid",
        "extra_agent_rules": extra_agent_rule_names,
        "flow": flow,
        "source_labels": True,
        "tool_previews": True,
        "citations": "sentence numbers",
        "refusal": refusal_setting,
        "max_answer_tokens": MAX_ANSWER_TOKENS,
        "answer_model": settings.mistral_answer_model,
        "reasoning_effort": settings.mistral_reasoning_effort,
        "judge_model": settings.claude_judge_model,
    }
    print(f"saved {run_name}-answers.jsonl and {run_name}-grades.jsonl in evals/answer_runs/", flush=True)
    if is_dry_run:
        print("dry run: not logged to evals/runs.jsonl")
        return scores
    append_run("3", run_settings, scores, seconds)
    return scores


def main() -> None:
    """Runs the agent setup named on the command line."""
    parser = argparse.ArgumentParser(description="Answer, check and grade the questions with an agent setup (Stage 3).")
    parser.add_argument("--setup", required=True, choices=SETUP_NAMES)
    parser.add_argument("--unseen", action="store_true", help="answer the unseen questions, once per setup")
    parser.add_argument("--agent-rule", action="append", default=[], choices=list(EXTRA_AGENT_RULES),
                        help="an extra agent rule to test; repeat for more than one")
    parser.add_argument("--no-agent-rules", action="store_true", help="no extra agent rules, as before record 0022")
    parser.add_argument("--flow", default=DEFAULT_FLOW, choices=list(ANSWER_FUNCTION_BY_FLOW),
                        help="one-call (slice 4) or gather-write (slice 5)")
    parser.add_argument("--label", help="a short name for the run (default: the setup name)")
    parser.add_argument("--dry-run", action="store_true", help="answer only the first question, and don't log the run")
    arguments = parser.parse_args()

    # Record 0022: a run uses both agent rules unless rules are named or turned off
    agent_rule_names = arguments.agent_rule
    uses_default_rules = not agent_rule_names and not arguments.no_agent_rules
    if uses_default_rules:
        agent_rule_names = list(DEFAULT_AGENT_RULE_NAMES)

    # Name the run by its setup, rules and question set, unless a label is given
    label = arguments.label
    if label is None:
        label = "-".join([arguments.setup] + agent_rule_names)
        if arguments.flow != DEFAULT_FLOW:
            label = f"{label}-{arguments.flow}"
        if arguments.unseen:
            label = f"{label}-unseen"
    if arguments.dry_run:
        label = f"{label}-dry-run"
    run_agent_setup(arguments.setup, label, arguments.dry_run, arguments.unseen, agent_rule_names, arguments.flow)


if __name__ == "__main__":
    main()
