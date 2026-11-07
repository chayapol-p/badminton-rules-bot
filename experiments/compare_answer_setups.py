"""
Answers the dev questions and the refusal probes with one setup, checks and grades every answer, prints the scores and logs the run.

One run changes one thing (experiment rule 1). Fixed here: vector search on the clauses'
search_text (decision record 0006), the answer model at temperature 0, and the judge.
  --top-k   clauses handed to the model per question (default 5)
  --label   a short name for the run, used in its file names (default: top<k>)
  --dry-run answer only the first question, for a cheap live check of the API settings before a
            full run. It saves its files under a "-dry-run" name and never logs to runs.jsonl

Writes, for each run:
  evals/answer_runs/<time>-<label>-answers.jsonl  per question: the sources, the answer and the code checks
  evals/answer_runs/<time>-<label>-grades.jsonl   per question: the judge's grade
The two files are kept apart, so you can grade answers yourself before you see the judge's grades.
Each line is saved as soon as its question is done, so a crash partway keeps every answer
already paid for. Only a finished run adds its line to evals/runs.jsonl.

Needs the saved question and probe vectors (run scripts.build_embeddings first) and both API
keys in .env. A run makes 33 answer calls and 33 judge calls.

Run from the project root:
    uv run python -m experiments.compare_answer_setups --top-k 5 --dry-run
    uv run python -m experiments.compare_answer_setups --top-k 5
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import numpy
from anthropic import Anthropic
from mistralai.client import Mistral

from answer.generate_answer import generate_answer
from answer.check_citations import find_citation_problems
from answer.check_refusals import CORRECT_REFUSAL, FALSE_REFUSAL, refusal_outcome, should_refuse
from app.settings import load_settings
from evals.golden_answer_chunks import load_chunks, load_questions
from evals.judge_answers import grade_answer, judge_passed
from evals.log_eval_run import append_run
from evals.refusal_probes import load_refusal_probes
from evals.token_costs import call_cost
from retrieval.stored_embeddings import load_embeddings
from retrieval.vector_search import VectorSearch


# Constants
## Clauses handed to the model per question, unless --top-k says otherwise
DEFAULT_TOP_K = 5

## Pause between questions, to stay under the APIs' requests-per-second limits
SECONDS_BETWEEN_QUESTIONS = 1.0

## Questions whose pass rule needs an image: a text-only answer fails them until images arrive in Week 4
IMAGE_ONLY_QUESTION_IDS = {"doubles-court-size", "service-judge-height-signal"}

## Where each run's answers and grades go
ANSWER_RUNS_FOLDER = Path(__file__).resolve().parent.parent / "evals" / "answer_runs"


# ===== The search, fixed by decision record 0006 =====

def build_clause_vector_search(chunks: list[dict], questions: list[dict], model: str) -> VectorSearch:
    """Returns vector search over the clauses' search_text, reading saved vectors for the clauses and the questions."""
    chunk_vector_by_id = load_embeddings("clauses_search_text", model)
    chunk_vectors = numpy.array([chunk_vector_by_id[chunk["id"]] for chunk in chunks])

    # Golden questions and probes are saved as two sets; the search looks each one up by its text
    question_vector_by_id = load_embeddings("questions", model)
    question_vector_by_id.update(load_embeddings("refusal_probes", model))
    question_vector_by_text = {}
    for question in questions:
        question_vector_by_text[question["question"]] = question_vector_by_id[question["id"]]

    def saved_question_vector(question_text: str) -> numpy.ndarray:
        """Returns the saved vector of a golden question or probe, found by its text."""
        return question_vector_by_text[question_text]

    return VectorSearch(chunks, chunk_vectors, embedding_function=saved_question_vector)


# ===== One question =====

def answer_and_grade(question: dict, search, top_k: int, mistral_client: Mistral, answer_model: str,
                     reasoning_effort: str, anthropic_client: Anthropic, judge_model: str) -> tuple[dict, dict]:
    """Returns one question's answer line (sources, answer, code checks) and its grade line (the judge's grade)."""

    # Retrieve, then answer from what was retrieved
    retrieved_chunks = search(question["question"], top_k)
    reply = generate_answer(mistral_client, answer_model, reasoning_effort, question["question"], retrieved_chunks)
    answer_line = {
        "id": question["id"],
        "split": question["split"],
        "category": question["category"],
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
        "answer_cost": call_cost(answer_model, reply.input_tokens, reply.output_tokens),
        "judge_cost": 0.0,
    }

    # A reply that didn't fit the shape can't be checked or graded: it counts as a fail, and its raw text is kept for Step 6
    if reply.is_format_error:
        answer_line["raw_reply"] = reply.raw_reply
        return answer_line, {"id": question["id"], "passed": False, "grade": None}

    # Code checks first, then the judge
    answer_line["answer"] = reply.answer.model_dump()
    answer_line["citation_problems"] = find_citation_problems(reply.answer, retrieved_chunks)
    answer_line["refusal_outcome"] = refusal_outcome(question, reply.answer.refused)
    grade_reply = grade_answer(anthropic_client, judge_model, question, reply.answer, retrieved_chunks)
    answer_line["judge_cost"] = call_cost(judge_model, grade_reply.input_tokens, grade_reply.output_tokens)
    grade_line = {"id": question["id"], "passed": judge_passed(grade_reply.grade), "grade": grade_reply.grade.model_dump()}
    return answer_line, grade_line


# ===== Scoring a run =====

def count_passed(answer_lines: list[dict], passed_by_id: dict[str, bool]) -> int:
    """Returns how many of the answers the judge passed."""
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

    # Split the questions into the groups each score reads
    answerable = [line for line in answer_lines if not line["should_refuse"]]
    text_answerable = [line for line in answerable if line["id"] not in IMAGE_ONLY_QUESTION_IDS]
    image_only = [line for line in answerable if line["id"] in IMAGE_ONLY_QUESTION_IDS]
    no_answer = [line for line in answer_lines if line["should_refuse"]]
    golden_no_answer = [line for line in no_answer if line["split"] != "probe"]
    probes = [line for line in no_answer if line["split"] == "probe"]
    with_answer = [line for line in answer_lines if not line["is_format_error"]]

    # Answers the judge passed, overall and per category
    answers_passed = count_passed(text_answerable, passed_by_id)
    by_category = {}
    for category in sorted({line["category"] for line in text_answerable}):
        same_category = [line for line in text_answerable if line["category"] == category]
        by_category[category] = {"passed": count_passed(same_category, passed_by_id), "questions": len(same_category)}

    # Code checks: citations, and refusals counted both ways
    citations_clean = [line for line in with_answer if not line["citation_problems"]]
    correct_refusals = [line for line in golden_no_answer if line["refusal_outcome"] == CORRECT_REFUSAL]
    correct_probe_refusals = [line for line in probes if line["refusal_outcome"] == CORRECT_REFUSAL]
    false_refusals = [line for line in answerable if line["refusal_outcome"] == FALSE_REFUSAL]

    # Cost of every call, answer and judge together
    costs = [line["answer_cost"] + line["judge_cost"] for line in answer_lines]

    return {
        "answers_passed": answers_passed,
        "answers_scored": len(text_answerable),
        "answer_pass_rate": share(answers_passed, len(text_answerable)),
        "by_category": by_category,
        "image_only_passed": count_passed(image_only, passed_by_id),
        "image_only_scored": len(image_only),
        "citation_pass_rate": share(len(citations_clean), len(with_answer)),
        "refusals_correct": len(correct_refusals),
        "refusals_needed": len(golden_no_answer),
        "probe_refusals_correct": len(correct_probe_refusals),
        "probes": len(probes),
        "no_answer_judged_passed": count_passed(golden_no_answer + probes, passed_by_id),
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
    print(f"citations clean {scores['citation_pass_rate']}  · format errors {scores['format_errors']}")
    print(f"refusals {scores['refusals_correct']} of {scores['refusals_needed']}  · probes {scores['probe_refusals_correct']} "
          f"of {scores['probes']}  · no-answer judged passed {scores['no_answer_judged_passed']} of "
          f"{scores['refusals_needed'] + scores['probes']}  · false refusals {scores['false_refusals']}")
    print(f"words per question {scores['words_returned']}  · cost per question ${scores['cost_per_question']}"
          f"  · total ${scores['total_cost']}")

    # One line per failure: what went wrong, so Step 6 can tag a cause
    for line in answer_lines:
        problems = [problem["problem"] for problem in line["citation_problems"]]
        judged_failed = not passed_by_id[line["id"]]
        if not judged_failed and not problems:
            continue

        judge_verdict = "pass"
        if judged_failed:
            judge_verdict = "fail"
        citation_verdict = "clean"
        if problems:
            citation_verdict = ", ".join(problems)
        print(f"  fail: {line['id']}  judge {judge_verdict}  refusal {line['refusal_outcome']}  citations {citation_verdict}")


def append_line(path: Path, line: dict) -> None:
    """Adds one JSON object as the last line of the file, which is saved when the file closes."""
    with path.open("a", encoding="utf-8") as output_file:
        output_file.write(json.dumps(line, ensure_ascii=False) + "\n")


# ===== Running one setup =====

def run_answer_setup(top_k: int, label: str, is_dry_run: bool) -> dict:
    """Answers, checks and grades every dev question and probe, then prints, saves and logs the run."""
    settings = load_settings()
    chunks = load_chunks()
    questions = load_questions("dev") + load_refusal_probes()

    # A dry run asks one question, to meet any API error that only the live server raises for under a cent
    if is_dry_run:
        questions = questions[:1]
    search = build_clause_vector_search(chunks, questions, settings.mistral_embedding_model).search
    mistral_client = Mistral(api_key=settings.mistral_api_key.get_secret_value())
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
        answer_line, grade_line = answer_and_grade(question, search, top_k, mistral_client, settings.mistral_answer_model,
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
        "split": "dev+probes",
        "top_k": top_k,
        "answer_model": settings.mistral_answer_model,
        "reasoning_effort": settings.mistral_reasoning_effort,
        "judge_model": settings.claude_judge_model,
    }
    print(f"saved {run_name}-answers.jsonl and {run_name}-grades.jsonl in evals/answer_runs/")

    # A dry run checks the settings, not the setup: it never counts as a result
    if is_dry_run:
        print("dry run: not logged to evals/runs.jsonl")
        return scores
    append_run("2", run_settings, scores, seconds)
    return scores


def main() -> None:
    """Runs the one setup named on the command line."""
    parser = argparse.ArgumentParser(description="Answer, check and grade the dev questions and refusal probes.")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--label", help="a short name for the run (default: top<k>)")
    parser.add_argument("--dry-run", action="store_true", help="answer only the first question, and don't log the run")
    arguments = parser.parse_args()
    label = arguments.label
    if label is None:
        label = f"top{arguments.top_k}"
    if arguments.dry_run:
        label = f"{label}-dry-run"
    run_answer_setup(arguments.top_k, label, arguments.dry_run)


if __name__ == "__main__":
    main()
