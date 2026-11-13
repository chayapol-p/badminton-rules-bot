"""
Answers the dev questions and the probes with one setup, checks and grades every answer, prints the scores and logs the run.

One run changes one thing (experiment rule 1). Fixed here: vector search on the clauses'
search_text (decision record 0006), the top 5 plus the clauses they link to (records 0009 and 0017)
and the items under a found list heading (record 0015), source blocks with the headings above each
clause (record 0017), the answer rules (records 0010 and 0015), the answer model at temperature 0,
and the judge (record 0014).
  --top-k   clauses search hands on per question, before the rule links are added (default 5)
  --rule    an extra answer rule to test, by name (answer/build_answer_prompt.py EXTRA_ANSWER_RULES);
            repeat it for more than one
  --held-out  answer the held-out questions instead of dev and the probes: once, for the published
            number (experiment rule 4). Never tune on its result
  --unseen  answer the unseen questions instead (Stage 3): once per setup, read question by question
            against each one's "needs" tag. Never tune on its result
  --label   a short name for the run, used in its file names (default: top<k>, then each rule name)
  --dry-run answer only the first question, for a cheap live check of the API settings before a
            full run. It saves its files under a "-dry-run" name and never logs to runs.jsonl

Writes, for each run:
  evals/answer_runs/<time>-<label>-answers.jsonl  per question: the sources, the answer and the code checks
  evals/answer_runs/<time>-<label>-grades.jsonl   per question: the judge's grade, or none when the code checks failed it
The two files are kept apart, so you can grade answers yourself before you see the judge's grades.
Each line is saved as soon as its question is done, so a crash partway keeps every answer
already paid for. Only a finished run adds its line to evals/runs.jsonl.

Needs the saved question and probe vectors (run scripts.build_embeddings first) and both API
keys in .env. A run makes 33 answer calls, and a judge call only for each answer that passes the
code checks (evals/code_checks.py): code decides what it can, the judge grades the rest.

Run from the project root:
    uv run python -m experiments.compare_answer_setups --top-k 5 --dry-run
    uv run python -m experiments.compare_answer_setups --top-k 5
    uv run python -m experiments.compare_answer_setups --prompt-version 2
"""

import argparse
import time
from collections.abc import Callable
from datetime import datetime, timezone
from statistics import mean

import numpy
from anthropic import Anthropic
from mistralai.client import Mistral
from mistralai.client.utils import BackoffStrategy, RetryConfig

from answer.answer_shape import RulesAnswer
from answer.build_answer_prompt import EXTRA_ANSWER_RULES, build_answer_rules
from answer.generate_answer import MAX_ANSWER_TOKENS, generate_answer
from answer.check_citations import find_citation_problems
from answer.check_refusals import CORRECT_REFUSAL, FALSE_REFUSAL, refusal_outcome, should_refuse
from app.settings import load_settings
from evals.answer_run_files import ANSWER_RUNS_FOLDER, append_line
from evals.golden_answer_chunks import load_chunks, load_questions
from evals.code_checks import find_code_failures
from evals.judge_answers import grade_answer, judge_passed
from evals.log_eval_run import append_run
from evals.probes import load_probes, load_unseen_questions
from evals.token_costs import call_cost
from retrieval.stored_embeddings import embeddings_file, load_embeddings
from retrieval.build_bundle import build_bundle, full_chunks
from retrieval.expand_with_rule_links import load_rule_map
from retrieval.vector_search import VectorSearch


# Constants
## Clauses handed to the model per question, unless --top-k says otherwise
DEFAULT_TOP_K = 5

## Pause between questions, to stay under the APIs' requests-per-second limits
SECONDS_BETWEEN_QUESTIONS = 1.0

## The SDK's own retry on a rate limit (429) or a server error: wait 2 s, doubling up to 60 s, for at
## most 5 minutes. Top 15 hit Mistral's rate limit on 8 Nov and lost the run at question 15
MISTRAL_RETRY = RetryConfig("backoff", BackoffStrategy(2_000, 60_000, 2.0, 300_000), retry_connection_errors=True)

## Questions whose pass rule needs an image: a text-only answer fails them until images arrive in Week 4
IMAGE_ONLY_QUESTION_IDS = {"doubles-court-size", "service-judge-height-signal"}

## Each code check, and the start of its failure messages
CODE_CHECK_PREFIXES = {
    "format error": ("format error",),
    "wrong refusal": ("missed refusal", "false refusal"),
    "citation problem": ("citation",),
    "wrong clause": ("wrong clause",),
}
CODE_CHECK_NAMES = list(CODE_CHECK_PREFIXES)


# ===== The search, fixed by decision record 0006 =====

def build_clause_vector_search(chunks: list[dict], questions: list[dict], model: str) -> VectorSearch:
    """Returns vector search over the clauses' search_text, reading saved vectors for the clauses and the questions."""
    chunk_vector_by_id = load_embeddings("clauses_search_text", model)
    chunk_vectors = numpy.array([chunk_vector_by_id[chunk["id"]] for chunk in chunks])

    # Golden questions, the two probe kinds and the unseen questions are saved as separate sets; the search looks each one up by its text
    question_vector_by_id = load_embeddings("questions", model)
    question_vector_by_id.update(load_embeddings("refusal_probes", model))
    question_vector_by_id.update(load_embeddings("false_premise_probes", model))

    # The unseen questions (Stage 3) join once their vectors are saved, so older runs still work without them
    if embeddings_file("unseen_questions").exists():
        question_vector_by_id.update(load_embeddings("unseen_questions", model))
    # Every question needs its vector, so a missing one stops the run before the first paid call
    question_vector_by_text = {}
    for question in questions:
        if question["id"] not in question_vector_by_id:
            raise KeyError(f"no saved vector for the question {question['id']!r}: run scripts.build_embeddings first")
        question_vector_by_text[question["question"]] = question_vector_by_id[question["id"]]

    def saved_question_vector(question_text: str) -> numpy.ndarray:
        """Returns the saved vector of a golden question or probe, found by its text."""
        return question_vector_by_text[question_text]

    return VectorSearch(chunks, chunk_vectors, embedding_function=saved_question_vector)


def build_retrieve_function(search: Callable, top_k: int, chunk_by_id: dict[str, dict],
                            rule_map: dict) -> Callable[[str], list[dict]]:
    """Returns the retrieve step: the top k from search, and the bundle the rule map builds for them (records 0009, 0015, 0023)."""

    def retrieve(question_text: str) -> list[dict]:
        """Returns the bundle handed to the answer model for one question: every clause in full, with its role label."""
        hits = search(question_text, top_k)
        hit_ids = [chunk["id"] for chunk in hits]
        return build_bundle(hit_ids, chunk_by_id, rule_map, related_in_full=True)

    return retrieve


# ===== One question =====

def answer_and_grade(question: dict, retrieve: Callable[[str], list[dict]], answer_rules: str, chunks: list[dict],
                     chunk_by_id: dict[str, dict], mistral_client: Mistral, answer_model: str, reasoning_effort: str,
                     anthropic_client: Anthropic, judge_model: str) -> tuple[dict, dict]:
    """Returns one question's answer line (sources, answer, code checks) and its grade line (the judge's grade, if judged)."""

    # Retrieve, then answer from what was retrieved
    source_items = retrieve(question["question"])
    retrieved_chunks = full_chunks(source_items)
    reply = generate_answer(mistral_client, answer_model, reasoning_effort, answer_rules, question["question"],
                            source_items)
    answer_line = {
        "id": question["id"],
        "split": question["split"],
        "category": question["category"],
        "needs": question.get("needs"),
        "question": question["question"],
        "should_refuse": should_refuse(question),
        "retrieved_ids": [chunk["id"] for chunk in retrieved_chunks],
        "words_returned": sum(len(chunk["text"].split()) for chunk in retrieved_chunks),
        "answer": None,
        "is_format_error": reply.is_format_error,
        "error_message": reply.error_message,
        "thinking": reply.thinking,
        "citation_problems": [],
        "refusal_outcome": None,
        "code_failures": ["format error"],
        "code_warnings": [],
        "answer_cost": call_cost(answer_model, reply.input_tokens, reply.output_tokens),
        "judge_cost": 0.0,
    }

    # A reply that didn't fit the shape can't be checked or graded: it counts as a fail, and its raw text is kept for Step 6
    if reply.is_format_error:
        answer_line["raw_reply"] = reply.raw_reply
        return answer_line, {"id": question["id"], "passed": False, "judged": False, "grade": None}

    answer_line["answer"] = reply.answer.model_dump()
    grade_line = check_and_grade(answer_line, reply.answer, question, retrieved_chunks, chunks, chunk_by_id,
                                 anthropic_client, judge_model)
    return answer_line, grade_line


def check_and_grade(answer_line: dict, rules_answer: RulesAnswer, question: dict, retrieved_chunks: list[dict],
                    chunks: list[dict], chunk_by_id: dict[str, dict], anthropic_client: Anthropic,
                    judge_model: str) -> dict:
    """Runs the code checks on one answer, then the judge when they pass; fills in the answer line's checks and judge cost, and returns the grade line."""

    # Code checks first: an answer they fail has failed, and isn't sent to the judge
    answer_line["citation_problems"] = find_citation_problems(rules_answer, retrieved_chunks)
    answer_line["refusal_outcome"] = refusal_outcome(question, rules_answer.refused)
    failures, warnings = find_code_failures(answer_line, question, chunks, chunk_by_id)
    answer_line["code_failures"] = failures
    answer_line["code_warnings"] = warnings
    answer_line["judge_cost"] = 0.0
    if failures:
        return {"id": question["id"], "passed": False, "judged": False, "grade": None}

    # Then the judge, for what only it can grade, with the code warnings to weigh
    grade_reply = grade_answer(anthropic_client, judge_model, question, rules_answer, retrieved_chunks, warnings)
    answer_line["judge_cost"] = call_cost(judge_model, grade_reply.input_tokens, grade_reply.output_tokens)
    return {"id": question["id"], "passed": judge_passed(grade_reply.grade), "judged": True,
            "grade": grade_reply.grade.model_dump()}


# ===== Scoring a run =====

def failed_check(answer_line: dict, check_name: str) -> bool:
    """True when one of the answer's code failures belongs to the named check."""
    prefixes = CODE_CHECK_PREFIXES[check_name]
    for failure in answer_line["code_failures"]:
        if failure.startswith(prefixes):
            return True
    return False


def count_passed(answer_lines: list[dict], passed_by_id: dict[str, bool]) -> int:
    """Returns how many of the answers passed: the code checks, then the judge."""
    passed_count = 0
    for line in answer_lines:
        if passed_by_id[line["id"]]:
            passed_count += 1
    return passed_count


def share(count: int, total: int) -> float:
    """Returns count / total rounded to 3 places, or 0.0 when there is nothing to count."""
    if total == 0:
        return 0.0
    return round(count / total, 3)


def summarise_answer_run(answer_lines: list[dict], passed_by_id: dict[str, bool]) -> dict:
    """Returns the run's scores: answers, diagrams, citations, refusals both ways, format errors, words and cost."""

    # Split the questions into the groups each score reads; probes are scored on their own lines
    answerable = [line for line in answer_lines if not line["should_refuse"] and line["split"] != "probe"]
    text_answerable = [line for line in answerable if line["id"] not in IMAGE_ONLY_QUESTION_IDS]
    image_only = [line for line in answerable if line["id"] in IMAGE_ONLY_QUESTION_IDS]
    no_answer = [line for line in answer_lines if line["should_refuse"]]
    golden_no_answer = [line for line in no_answer if line["split"] != "probe"]
    probes = [line for line in no_answer if line["split"] == "probe"]
    false_premises = [line for line in answer_lines if line["category"] == "false_premise"]
    with_answer = [line for line in answer_lines if not line["is_format_error"]]

    # Answers the judge passed, overall and per category
    answers_passed = count_passed(text_answerable, passed_by_id)
    by_category = {}
    for category in sorted({line["category"] for line in text_answerable}):
        same_category = [line for line in text_answerable if line["category"] == category]
        by_category[category] = {"passed": count_passed(same_category, passed_by_id), "questions": len(same_category)}

    # Unseen questions: answers passed per needs tag, the reading Stage 3 compares setups on
    by_needs = {}
    for needs in sorted({line["needs"] for line in answer_lines if line.get("needs")}):
        same_needs = [line for line in answer_lines if line.get("needs") == needs]
        by_needs[needs] = {"passed": count_passed(same_needs, passed_by_id), "questions": len(same_needs)}

    # Code checks: what failed them, by check, and how many answers went on to the judge
    code_failed = [line for line in answer_lines if line["code_failures"]]
    code_failures_by_check = {}
    for check_name in CODE_CHECK_NAMES:
        failed_lines = [line for line in code_failed if failed_check(line, check_name)]
        code_failures_by_check[check_name] = len(failed_lines)

    # Citations, and refusals counted both ways
    citations_clean = [line for line in with_answer if not line["citation_problems"]]
    correct_refusals = [line for line in golden_no_answer if line["refusal_outcome"] == CORRECT_REFUSAL]
    correct_probe_refusals = [line for line in probes if line["refusal_outcome"] == CORRECT_REFUSAL]
    # Image-only questions are left out: refusing them is fair until images arrive in Week 4
    false_refusals = [line for line in text_answerable if line["refusal_outcome"] == FALSE_REFUSAL]

    # Cost of every call, answer and judge together
    costs = [line["answer_cost"] + line["judge_cost"] for line in answer_lines]

    return {
        "answers_passed": answers_passed,
        "answers_scored": len(text_answerable),
        "answer_pass_rate": share(answers_passed, len(text_answerable)),
        "by_category": by_category,
        "by_needs": by_needs,
        "image_only_passed": count_passed(image_only, passed_by_id),
        "image_only_scored": len(image_only),
        "citation_pass_rate": share(len(citations_clean), len(with_answer)),
        "refusals_correct": len(correct_refusals),
        "refusals_needed": len(golden_no_answer),
        "probe_refusals_correct": len(correct_probe_refusals),
        "probes": len(probes),
        "no_answer_passed": count_passed(golden_no_answer + probes, passed_by_id),
        "false_premise_passed": count_passed(false_premises, passed_by_id),
        "false_premise_probes": len(false_premises),
        "code_failed": len(code_failed),
        "code_failures_by_check": code_failures_by_check,
        "judge_calls": len(answer_lines) - len(code_failed),
        "false_refusals": len(false_refusals),
        "format_errors": len(answer_lines) - len(with_answer),
        "words_returned": round(mean(line["words_returned"] for line in answer_lines)),
        "cost_per_question": round(mean(costs), 4),
        "total_cost": round(sum(costs), 3),
    }


# ===== Printing and saving =====

def print_scores(scores: dict, answer_lines: list[dict], passed_by_id: dict[str, bool]) -> None:
    """Prints the scores, then every question that failed a check or the judge, for Step 6."""
    print(f"answers  {scores['answers_passed']} of {scores['answers_scored']} passed ({scores['answer_pass_rate']})"
          f"  · image-only {scores['image_only_passed']} of {scores['image_only_scored']}")
    for category, numbers in scores["by_category"].items():
        print(f"  {category:16} {numbers['passed']} of {numbers['questions']}")
    for needs, numbers in scores["by_needs"].items():
        print(f"  needs {needs:12} {numbers['passed']} of {numbers['questions']}")
    print(f"citations clean {scores['citation_pass_rate']}  · format errors {scores['format_errors']}")
    print(f"code checks failed {scores['code_failed']}  {scores['code_failures_by_check']}  · judge calls {scores['judge_calls']}")
    print(f"refusals {scores['refusals_correct']} of {scores['refusals_needed']}  · probes {scores['probe_refusals_correct']} "
          f"of {scores['probes']}  · no-answer passed {scores['no_answer_passed']} of "
          f"{scores['refusals_needed'] + scores['probes']}  · false refusals {scores['false_refusals']}")
    print(f"false premises corrected and answered {scores['false_premise_passed']} of {scores['false_premise_probes']}")
    print(f"words per question {scores['words_returned']}  · cost per question ${scores['cost_per_question']}"
          f"  · total ${scores['total_cost']}")

    # One line per failure: the code checks it failed, or the judge's fail, so Step 6 can tag a cause
    for line in answer_lines:
        if passed_by_id[line["id"]]:
            continue
        reason = "judge fail"
        if line["code_failures"]:
            reason = "; ".join(line["code_failures"])
        print(f"  fail: {line['id']}  {reason}")


# ===== Running one setup =====

def run_answer_setup(top_k: int, extra_rule_names: list[str], label: str, is_dry_run: bool,
                     uses_held_out: bool, uses_unseen: bool = False) -> dict:
    """Answers, checks and grades every dev question and probe, then prints, saves and logs the run."""
    settings = load_settings()
    chunks = load_chunks()
    questions = load_questions("dev") + load_probes()
    split_name = "dev+probes"
    stage = "2"
    if uses_held_out:
        questions = load_questions("held_out")
        split_name = "held_out"
    if uses_unseen:
        questions = load_unseen_questions()
        split_name = "unseen"
        stage = "3"

    # A dry run asks one question, to meet any API error that only the live server raises for under a cent
    if is_dry_run:
        questions = questions[:1]
    search = build_clause_vector_search(chunks, questions, settings.mistral_embedding_model).search
    chunk_by_id = {chunk["id"]: chunk for chunk in chunks}
    retrieve = build_retrieve_function(search, top_k, chunk_by_id, load_rule_map())
    answer_rules = build_answer_rules(extra_rule_names)
    mistral_client = Mistral(api_key=settings.mistral_api_key.get_secret_value(), retry_config=MISTRAL_RETRY)
    anthropic_client = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())

    # Name the run first, so each answer can be saved the moment it's done
    run_name = f"{datetime.now(timezone.utc):%Y%m%dT%H%M}-{label}"
    ANSWER_RUNS_FOLDER.mkdir(parents=True, exist_ok=True)
    answers_path = ANSWER_RUNS_FOLDER / f"{run_name}-answers.jsonl"
    grades_path = ANSWER_RUNS_FOLDER / f"{run_name}-grades.jsonl"

    # Answer and grade each question, and save both lines before asking the next one,
    # so a crash partway loses nothing already paid for. Pause between questions for the rate limits
    started = time.perf_counter()
    answer_lines = []
    grade_lines = []
    for question_number, question in enumerate(questions, start=1):
        print(f"{question_number}/{len(questions)} {question['id']}")
        answer_line, grade_line = answer_and_grade(question, retrieve, answer_rules, chunks, chunk_by_id,
                                                   mistral_client, settings.mistral_answer_model,
                                                   settings.mistral_reasoning_effort, anthropic_client,
                                                   settings.claude_judge_model)
        append_line(answers_path, answer_line)
        append_line(grades_path, grade_line)
        answer_lines.append(answer_line)
        grade_lines.append(grade_line)
        time.sleep(SECONDS_BETWEEN_QUESTIONS)
    seconds = time.perf_counter() - started

    # Score and print, then log the run: only a finished run gets a line in runs.jsonl
    passed_by_id = {line["id"]: line["passed"] for line in grade_lines}
    scores = summarise_answer_run(answer_lines, passed_by_id)
    print_scores(scores, answer_lines, passed_by_id)
    run_settings = {
        "run": run_name,
        "search": "vector",
        "chunks": "clauses",
        "field": "search_text",
        "split": split_name,
        "top_k": top_k,
        "rule_links": True,
        "list_items": True,
        "show_parents": True,
        "source_labels": True,
        "citations": "sentence numbers",
        "refusal": "code, from the parts",
        "max_answer_tokens": MAX_ANSWER_TOKENS,
        "extra_rules": extra_rule_names,
        "answer_model": settings.mistral_answer_model,
        "reasoning_effort": settings.mistral_reasoning_effort,
        "judge_model": settings.claude_judge_model,
    }
    print(f"saved {run_name}-answers.jsonl and {run_name}-grades.jsonl in evals/answer_runs/")

    # A dry run checks the settings, not the setup: it never counts as a result
    if is_dry_run:
        print("dry run: not logged to evals/runs.jsonl")
        return scores
    append_run(stage, run_settings, scores, seconds)
    return scores


def main() -> None:
    """Runs the one setup named on the command line."""
    parser = argparse.ArgumentParser(description="Answer, check and grade the dev questions and probes.")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    question_sets = parser.add_mutually_exclusive_group()
    question_sets.add_argument("--held-out", action="store_true", help="answer the held-out questions, once, for the published number")
    question_sets.add_argument("--unseen", action="store_true", help="answer the unseen questions (Stage 3), once per setup")
    parser.add_argument("--rule", action="append", default=[], choices=list(EXTRA_ANSWER_RULES),
                        help="an extra answer rule to test; repeat for more than one")
    parser.add_argument("--label", help="a short name for the run (default: top<k>, then each rule name)")
    parser.add_argument("--dry-run", action="store_true", help="answer only the first question, and don't log the run")
    arguments = parser.parse_args()

    # Name the run by what it changed, unless a label is given
    label = arguments.label
    if label is None:
        label = "-".join([f"top{arguments.top_k}"] + arguments.rule)
        if arguments.held_out:
            label = f"{label}-held-out"
        if arguments.unseen:
            label = f"{label}-unseen"
    if arguments.dry_run:
        label = f"{label}-dry-run"
    run_answer_setup(arguments.top_k, arguments.rule, label, arguments.dry_run, arguments.held_out, arguments.unseen)


if __name__ == "__main__":
    main()
