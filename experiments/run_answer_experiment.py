"""
Answers a question set with one setup and one answer flow, checks and grades every answer, prints the scores and logs the run.

A setup says where the model's sources come from; a flow says how it answers. Each setup allows only
the flows that fit it:

  setup       starting sources                       tools   flows (the first is the default)
  plain-rag   vector top k + rule links, all in full   no      single-call
  agentic     none                                     yes     loop-call-with-tools, gather-then-write,
                                                               gather-then-write-per-part
  hybrid      as plain-rag (record 0021)               yes     loop-call-with-tools, gather-then-write,
                                                               gather-then-write-per-part

  single-call           one call picks the sentences per part and writes the answer (experiments/retired_flows/single_call)
  loop-call-with-tools  the same, after a tool loop (slice 4, experiments/retired_flows/loop_call_with_tools)
  gather-then-write     a tool loop picks the sentences only, code refuses when no part has one, and a write
                        call with no tools writes one natural answer with inline [n] markers (slice 5 with
                        record 0027, answer_flows/gather_then_write)
  gather-then-write-per-part  slice 5 before record 0027: the write call answers each part on its own line
                        (experiments/retired_flows/gather_then_write_per_part)

One run changes one thing (experiment rule 1). Fixed for every run: vector search on the clauses'
search_text (record 0006), source blocks with the headings above each clause (record 0017), the answer
model at temperature 0 and the judge (record 0014).

  --setup         plain-rag | agentic | hybrid
  --flow          one of the setup's flows (default: its first)
  --top-k         clauses the starting search hands on, before the rule links (default 5; not for agentic)
  --rule          an extra answer limit to test, by name (experiments/retired_flows/single_call/answer_rules.py EXTRA_ANSWER_RULES);
                  repeat for more than one. Not for the gather-then-write flows, which have their own rules
  --agent-rule    an extra note to test in the tools section, by name (answer_flows/shared/tool_loop.py
                  EXTRA_AGENT_RULES; empty since record 0024 made the two default ones search steps). Tool setups only
  --held-out      answer the held-out questions: once, for the published number (experiment rule 4)
  --unseen        answer the unseen questions: once per setup, read against each one's "needs" tag
  --phase2        answer the Phase 2 questions (41 dev questions, 14 should refuse; slice 2)
  --label         a short name for the run, used in its file names
  --parallel      how many questions are answered and graded at once (default 1). Answers and grades don't
                  change: each question stands alone at temperature 0; only the order of lines in the run
                  files does. Too many at once can hit Mistral's rate limit, which the client retries
  --dry-run       answer only the first question, and don't log the run

Writes, for each run (each line saved as soon as its question is done, so a crash keeps what was paid for;
each answer line records the seconds its answer and its grading took):
  evals/answer_runs/<time>-<label>-answers.jsonl  per question: the sources, the answer, the tool use and the code checks
  evals/answer_runs/<time>-<label>-grades.jsonl   per question: the judge's grade (none for a format error) and its
                                                  scorecard, every line pass or fail (record 0027)
Only a finished run adds its line to evals/runs.jsonl.

Needs the saved question vectors (scripts.build_embeddings) and both API keys in .env.

Run from the project root:
    uv run python -m experiments.run_answer_experiment --setup plain-rag --dry-run
    uv run python -m experiments.run_answer_experiment --setup hybrid --unseen
    uv run python -m experiments.run_answer_experiment --setup hybrid --flow gather-then-write --dry-run
    uv run python -m experiments.run_answer_experiment --setup hybrid --phase2 --dry-run
"""

import argparse
import subprocess
import sys
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial

from anthropic import Anthropic
from mistralai.client import Mistral
from mistralai.client.errors import SDKError

from answer_flows.gather_then_write.gather_and_write_rules import GATHER_RULES
from answer_flows.gather_then_write.gather_then_write import gather_then_write
from answer_flows.shared.mistral_client import build_mistral_client
from answer_flows.shared.flow_reply import FlowReply
from answer_flows.shared.read_model_reply import MAX_ANSWER_TOKENS
from answer_flows.shared.rule_tools import RuleTools
from answer_flows.shared.tool_loop import EXTRA_AGENT_RULES
from app.settings import Settings, load_settings
from evals.answer_run_files import ANSWER_RUNS_FOLDER, append_line
from evals.checks.check_refusals import should_refuse
from evals.golden_answer_chunks import load_chunks, load_questions
from evals.log_eval_run import append_run
from evals.probes import load_phase2_questions, load_probes, load_unseen_questions
from evals.scorecard import build_scorecard, print_scorecard, summarise_scorecards
from evals.score_answer_run import (check_and_grade, print_scores, print_tool_use, summarise_answer_run,
                                    summarise_tool_use)
from evals.token_costs import call_cost
from experiments.retired_flows.gather_then_write_per_part.gather_and_write_rules import \
    GATHER_RULES as PER_PART_GATHER_RULES
from experiments.retired_flows.gather_then_write_per_part.gather_then_write import gather_then_write_per_part
from experiments.retired_flows.loop_call_with_tools.answer_with_tools import answer_with_tools
from experiments.retired_flows.single_call.answer_rules import EXTRA_ANSWER_RULES, build_answer_rules
from experiments.retired_flows.single_call.generate_answer import generate_answer
from retrieval.expand_with_rule_links import load_rule_map
from retrieval.retrieve_sources import (DEFAULT_TOP_K, build_clause_vector_search, build_live_vector_search,
                                        build_retrieve_function)


# Constants
## Pause between questions, to stay under the APIs' requests-per-second limits
SECONDS_BETWEEN_QUESTIONS = 1.0

## The SDK retries only 429, 500, 502, 503 and 504. On 17 Nov a Cloudflare 520 from Mistral ("retry after 60 s")
## stopped a whole run at one question, so any other server error retries the question here
QUESTION_ATTEMPTS = 3
SECONDS_BEFORE_QUESTION_RETRY = 60

## The answer flows that use tools, by their --flow name. Each takes the same arguments
TOOL_FLOW_FUNCTIONS = {"loop-call-with-tools": answer_with_tools, "gather-then-write": gather_then_write,
                       "gather-then-write-per-part": gather_then_write_per_part}

## The gather-then-write flows' own gather prompts, by --flow name
GATHER_RULES_BY_FLOW = {"gather-then-write": GATHER_RULES, "gather-then-write-per-part": PER_PART_GATHER_RULES}

## How each flow decides a refusal, as runs.jsonl records it
REFUSAL_BY_FLOW = {
    "single-call": "code, from the parts",
    "loop-call-with-tools": "code, from the parts",
    "gather-then-write": "code gate before the write call",
    "gather-then-write-per-part": "code gate before the write call",
}

# ===== The setups =====

@dataclass(frozen=True)
class Setup:
    """Where one setup's sources come from, and the answer flows that fit it (the first is the default)."""

    has_starting_sources: bool
    has_tools: bool
    flows: tuple[str, ...]


SETUPS = {
    "plain-rag": Setup(has_starting_sources=True, has_tools=False, flows=("single-call",)),
    "agentic": Setup(has_starting_sources=False, has_tools=True,
                     flows=("loop-call-with-tools", "gather-then-write", "gather-then-write-per-part")),
    "hybrid": Setup(has_starting_sources=True, has_tools=True,
                    flows=("loop-call-with-tools", "gather-then-write", "gather-then-write-per-part")),
}

## The stage every answer run logs since the measurement restarted with Phase 2 (record 0024)
MEASUREMENT_STAGE = "phase2"

## Every flow any setup allows
FLOW_NAMES = list(REFUSAL_BY_FLOW)


# ===== The command line =====

@dataclass
class RunChoices:
    """Everything one run is told on the command line, checked against what its setup allows."""

    setup_name: str
    flow: str
    top_k: int | None
    extra_rule_names: list[str]
    agent_rule_names: list[str]
    question_set: str
    label: str
    is_dry_run: bool
    parallel: int = 1


def build_parser() -> argparse.ArgumentParser:
    """Returns the command-line parser for one run."""
    parser = argparse.ArgumentParser(description="Answer, check and grade a question set with one setup and one flow.")
    parser.add_argument("--setup", required=True, choices=list(SETUPS))
    parser.add_argument("--flow", choices=FLOW_NAMES, help="one of the setup's flows (default: its first)")
    parser.add_argument("--top-k", type=int, help=f"clauses the starting search hands on (default {DEFAULT_TOP_K})")
    parser.add_argument("--rule", action="append", default=[], choices=list(EXTRA_ANSWER_RULES),
                        help="an extra answer rule to test; repeat for more than one")
    parser.add_argument("--agent-rule", action="append", default=[], choices=list(EXTRA_AGENT_RULES),
                        help="an extra agent rule to test; repeat for more than one")
    question_sets = parser.add_mutually_exclusive_group()
    question_sets.add_argument("--held-out", action="store_true", help="answer the held-out questions, once")
    question_sets.add_argument("--unseen", action="store_true", help="answer the unseen questions, once per setup")
    question_sets.add_argument("--phase2", action="store_true", help="answer the Phase 2 questions (slice 2)")
    parser.add_argument("--label", help="a short name for the run")
    parser.add_argument("--parallel", type=int, default=1, help="how many questions are answered at once (default 1)")
    parser.add_argument("--dry-run", action="store_true", help="answer only the first question, and don't log the run")
    return parser


def find_choice_problem(arguments: argparse.Namespace, setup: Setup, flow: str) -> str | None:
    """Returns why the choices don't fit the setup (a flow it doesn't allow, an option it has no use for), or None."""
    if flow not in setup.flows:
        return f"--setup {arguments.setup} allows the flows {', '.join(setup.flows)}, not {flow}"
    if arguments.top_k is not None and not setup.has_starting_sources:
        return f"--top-k: --setup {arguments.setup} has no starting sources"
    if arguments.agent_rule and not setup.has_tools:
        return f"--agent-rule: --setup {arguments.setup} has no tools"
    if arguments.parallel < 1:
        return f"--parallel must be 1 or more, not {arguments.parallel}"
    if arguments.rule and flow in GATHER_RULES_BY_FLOW:
        return f"--rule: {flow} has its own rules"
    return None


def build_label(arguments: argparse.Namespace, flow: str, top_k: int | None, agent_rule_names: list[str],
                question_set: str) -> str:
    """Returns the run's default name: what it changed, then the question set, as the old run files were named."""

    # plain-rag runs keep their old names (top5, then each rule); tool setups start with the setup and any extra agent rules
    if arguments.setup == "plain-rag":
        name_parts = [f"top{top_k}"] + arguments.rule
    else:
        name_parts = [arguments.setup] + agent_rule_names + arguments.rule
        if flow != SETUPS[arguments.setup].flows[0]:
            name_parts.append(flow)
    if question_set != "dev":
        name_parts.append(question_set)
    return "-".join(name_parts)


def parse_run_choices(command_line: list[str]) -> RunChoices:
    """Returns the run's choices from the command line; stops with a message when they don't fit the setup."""
    parser = build_parser()
    arguments = parser.parse_args(command_line)
    setup = SETUPS[arguments.setup]
    flow = arguments.flow or setup.flows[0]
    problem = find_choice_problem(arguments, setup, flow)
    if problem is not None:
        parser.error(problem)

    # A setup with starting sources uses the default top k unless told otherwise
    top_k = None
    if setup.has_starting_sources:
        top_k = arguments.top_k or DEFAULT_TOP_K
    agent_rule_names = arguments.agent_rule

    # The question set, and the run's name
    question_set = "dev"
    if arguments.held_out:
        question_set = "held-out"
    if arguments.unseen:
        question_set = "unseen"
    if arguments.phase2:
        question_set = "phase2"
    label = arguments.label or build_label(arguments, flow, top_k, agent_rule_names, question_set)
    if arguments.dry_run:
        label = f"{label}-dry-run"
    return RunChoices(setup_name=arguments.setup, flow=flow, top_k=top_k, extra_rule_names=arguments.rule,
                      agent_rule_names=agent_rule_names, question_set=question_set, label=label,
                      is_dry_run=arguments.dry_run, parallel=arguments.parallel)


# ===== The questions =====

def load_question_set(question_set: str) -> tuple[list[dict], str]:
    """Returns the questions of one set, and the split name runs.jsonl records for it."""
    if question_set == "held-out":
        return load_questions("held_out"), "held_out"
    if question_set == "unseen":
        return load_unseen_questions(), "unseen"
    if question_set == "phase2":
        return load_phase2_questions(), "phase2"
    return load_questions("dev") + load_probes(), "dev+probes"


# ===== One question =====

def answer_question(question_text: str, choices: RunChoices, retrieve: Callable[[str], list[dict]] | None,
                    rule_tools: RuleTools | None, answer_rules: str, mistral_client: Mistral,
                    settings: Settings) -> FlowReply:
    """Answers one question with the run's setup and flow."""

    # The starting sources, for the setups that have them
    starting_items = []
    if retrieve is not None:
        starting_items = retrieve(question_text)

    # single-call has no tools; the tool flows share one signature
    if choices.flow == "single-call":
        return generate_answer(mistral_client, settings.mistral_answer_model, settings.mistral_reasoning_effort,
                               answer_rules, question_text, starting_items)
    answer_function = TOOL_FLOW_FUNCTIONS[choices.flow]
    return answer_function(mistral_client, settings.mistral_answer_model, settings.mistral_reasoning_effort,
                           answer_rules, question_text, starting_items, rule_tools, choices.agent_rule_names)


def build_answer_line(question: dict, reply: FlowReply, answer_model: str) -> dict:
    """Returns one question's answer line before the checks: the sources, the reply and its tool use."""
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
        "gathered_parts": reply.gathered_parts,
        "bad_picks": reply.bad_picks,
        "write_called": reply.write_called,
        "write_reply": reply.write_reply,
        "answer_cost": call_cost(answer_model, reply.input_tokens, reply.output_tokens),
        "judge_cost": 0.0,
    }


def grade_reply(question: dict, reply: FlowReply, chunks: list[dict], chunk_by_id: dict[str, dict],
                anthropic_client: Anthropic, settings: Settings) -> tuple[dict, dict]:
    """Returns one question's answer line and grade line: the code checks, then the judge."""
    answer_line = build_answer_line(question, reply, settings.mistral_answer_model)

    # A reply that didn't fit the shape can't be checked or graded: it counts as a fail, with its raw text kept
    if reply.is_format_error:
        answer_line["raw_reply"] = reply.raw_reply
        return answer_line, {"id": question["id"], "passed": False, "judged": False, "grade": None,
                             "scorecard": build_scorecard(answer_line, None)}
    answer_line["answer"] = reply.answer.model_dump()
    grade_line = check_and_grade(answer_line, reply.answer, question, reply.shown_chunks, chunks, chunk_by_id,
                                 anthropic_client, settings.claude_judge_model)
    return answer_line, grade_line


def answer_and_grade(question: dict, choices: RunChoices, retrieve: Callable[[str], list[dict]] | None,
                     build_rule_tools: Callable[[], RuleTools] | None, answer_rules: str, mistral_client: Mistral,
                     anthropic_client: Anthropic, chunks: list[dict], chunk_by_id: dict[str, dict],
                     settings: Settings) -> tuple[dict, dict]:
    """Answers and grades one question, and records in its answer line how many seconds each took."""

    # Each question gets its own tools, because the tools remember which clauses this question has seen
    rule_tools = None
    if build_rule_tools is not None:
        rule_tools = build_rule_tools()

    # Answer, then grade, timing each
    started = time.perf_counter()
    reply = answer_question(question["question"], choices, retrieve, rule_tools, answer_rules, mistral_client, settings)
    answered = time.perf_counter()
    answer_line, grade_line = grade_reply(question, reply, chunks, chunk_by_id, anthropic_client, settings)
    answer_line["answer_seconds"] = round(answered - started, 1)
    answer_line["grade_seconds"] = round(time.perf_counter() - answered, 1)

    # A pause before this worker's next question, to stay under the APIs' requests-per-second limits
    time.sleep(SECONDS_BETWEEN_QUESTIONS)
    return answer_line, grade_line


def run_with_retries(answer_one_question: Callable[[], tuple[dict, dict]], question_id: str) -> tuple[dict, dict]:
    """Runs one question's answer and grade, trying again after a Mistral server error; stops the run when it keeps failing."""
    for attempt_number in range(1, QUESTION_ATTEMPTS + 1):
        try:
            return answer_one_question()
        except SDKError as error:
            # A client error (bad key, bad request) breaks every question, so it stops the run at once
            is_server_error = error.status_code >= 500
            if not is_server_error or attempt_number == QUESTION_ATTEMPTS:
                raise
            print(f"   {question_id}: Mistral server error {error.status_code}, retrying in "
                  f"{SECONDS_BEFORE_QUESTION_RETRY} s (attempt {attempt_number} of {QUESTION_ATTEMPTS})", flush=True)
            time.sleep(SECONDS_BEFORE_QUESTION_RETRY)


# ===== The code's version, for runs.jsonl =====

def read_code_version() -> dict:
    """Returns the git commit the run's code is at, and whether tracked files had changes not yet committed."""

    # Every run's settings record this, so a missing git stops the run before any paid call
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True)
    changed_files = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                   capture_output=True, text=True, check=True)

    # Untracked files (helper scripts in workshop/) don't change the code a run uses, so only tracked ones count
    has_uncommitted_changes = changed_files.stdout.strip() != ""
    return {"code_commit": commit.stdout.strip(), "code_has_uncommitted_changes": has_uncommitted_changes}


# ===== The run's settings, for runs.jsonl =====

def build_run_settings(run_name: str, choices: RunChoices, split_name: str, settings: Settings) -> dict:
    """Returns what runs.jsonl records about the run: the setup, the flow and every fixed setting."""
    setup = SETUPS[choices.setup_name]
    run_settings = {"run": run_name, "setup": choices.setup_name, "flow": choices.flow, "search": "vector",
                    "chunks": "clauses", "field": "search_text", "split": split_name,
                    "starting_sources": setup.has_starting_sources}

    # The starting sources' settings, and the tool settings, only for setups that have them
    if setup.has_starting_sources:
        run_settings.update({"top_k": choices.top_k, "rule_links": True, "list_items": True, "show_parents": True})
    if setup.has_tools:
        run_settings.update({"extra_agent_rules": choices.agent_rule_names, "tool_previews": True})
    run_settings.update({
        "source_labels": True,
        "prompt_layout": "task, steps, limits",
        "citations": "sentence numbers",
        "refusal": REFUSAL_BY_FLOW[choices.flow],
        "max_answer_tokens": MAX_ANSWER_TOKENS,
        "extra_rules": choices.extra_rule_names,
        "answer_model": settings.mistral_answer_model,
        "reasoning_effort": settings.mistral_reasoning_effort,
        "judge_model": settings.claude_judge_model,
        "questions_at_once": choices.parallel,
    })
    run_settings.update(read_code_version())
    return run_settings


# ===== One run =====

def run_answer_experiment(choices: RunChoices) -> dict:
    """Answers, checks and grades every question with one setup and flow, then prints, saves and logs the run."""
    settings = load_settings()
    setup = SETUPS[choices.setup_name]
    chunks = load_chunks()
    chunk_by_id = {chunk["id"]: chunk for chunk in chunks}
    rule_map = load_rule_map()
    questions, split_name = load_question_set(choices.question_set)

    # A dry run asks one question, to meet any API error that only the live server raises, for a few cents
    if choices.is_dry_run:
        questions = questions[:1]
    mistral_client = build_mistral_client(settings)
    anthropic_client = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())

    # The starting sources and the tools, for the setups that have them
    retrieve = None
    if setup.has_starting_sources:
        question_search = build_clause_vector_search(chunks, questions, settings.mistral_embedding_model).search
        retrieve = build_retrieve_function(question_search, choices.top_k, chunk_by_id, rule_map)
    build_rule_tools = None
    if setup.has_tools:
        live_search = build_live_vector_search(chunks, mistral_client, settings.mistral_embedding_model)

        def build_rule_tools() -> RuleTools:
            """Returns fresh tools for one question, sharing the search and its saved query vectors."""
            return RuleTools(chunks, live_search.search, rule_map)

    # The gather-then-write flows have their own gather prompts; the other flows use the answer prompt, with the
    # search steps when they have tools
    answer_rules = build_answer_rules(choices.extra_rule_names, uses_tools=setup.has_tools)
    if choices.flow in GATHER_RULES_BY_FLOW:
        answer_rules = GATHER_RULES_BY_FLOW[choices.flow]

    # Name the run first, so each answer can be saved the moment it's done
    run_name = f"{datetime.now(timezone.utc):%Y%m%dT%H%M}-{choices.label}"
    ANSWER_RUNS_FOLDER.mkdir(parents=True, exist_ok=True)
    answers_path = ANSWER_RUNS_FOLDER / f"{run_name}-answers.jsonl"
    grades_path = ANSWER_RUNS_FOLDER / f"{run_name}-grades.jsonl"

    # Answer and grade --parallel questions at a time; each pair of lines is saved the moment its question is done,
    # by this thread only, so a crash keeps what was paid for and two writes never mix
    started = time.perf_counter()
    answer_lines = []
    grade_lines = []
    with ThreadPoolExecutor(max_workers=choices.parallel) as executor:
        futures: list[Future] = []
        for question in questions:
            answer_one_question = partial(answer_and_grade, question, choices, retrieve, build_rule_tools, answer_rules,
                                          mistral_client, anthropic_client, chunks, chunk_by_id, settings)
            futures.append(executor.submit(run_with_retries, answer_one_question, question["id"]))

        # A question that raises stops the run, as before: the questions not started yet are cancelled
        try:
            for done_count, future in enumerate(as_completed(futures), start=1):
                answer_line, grade_line = future.result()
                print(f"{done_count}/{len(questions)} {answer_line['id']}  answer {answer_line['answer_seconds']} s"
                      f" · grade {answer_line['grade_seconds']} s", flush=True)
                append_line(answers_path, answer_line)
                append_line(grades_path, grade_line)
                answer_lines.append(answer_line)
                grade_lines.append(grade_line)
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    seconds = time.perf_counter() - started

    # Score and print; the tool setups add their tool use
    passed_by_id = {line["id"]: line["passed"] for line in grade_lines}
    scores = summarise_answer_run(answer_lines, passed_by_id)
    print_scores(scores, answer_lines, passed_by_id)
    scores["scorecard"] = summarise_scorecards(grade_lines)
    print_scorecard(scores["scorecard"])
    if setup.has_tools:
        scores["tool_use"] = summarise_tool_use(answer_lines)
        print_tool_use(scores["tool_use"])
    print(f"saved {run_name}-answers.jsonl and {run_name}-grades.jsonl in evals/answer_runs/", flush=True)

    # Only a finished, real run is logged. Measurement restarted with Phase 2 (Job, 13 Nov): every answer run from
    # here on is stage "phase2", so its numbers are read only against other phase2 runs, never Stage 2 or 3
    if choices.is_dry_run:
        print("dry run: not logged to evals/runs.jsonl")
        return scores
    append_run(MEASUREMENT_STAGE, build_run_settings(run_name, choices, split_name, settings), scores, seconds)
    return scores


def main() -> None:
    """Runs the setup and flow named on the command line."""
    run_answer_experiment(parse_run_choices(sys.argv[1:]))


if __name__ == "__main__":
    main()
