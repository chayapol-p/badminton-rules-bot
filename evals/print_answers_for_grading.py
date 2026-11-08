"""
Prints a run's answers in a readable form for grading by hand, without the judge's grades, and can start your grades file.

For each answer: the question, what a good reply needs (the golden answer or why there is none,
and the pass rule), the clauses the bot was shown, then the bot's reasoning, answer, citations
and the code checks. The judge's grades stay in their own file, so they can't steer yours.

  Input:  evals/answer_runs/<run>-answers.jsonl, evals/golden_questions.json,
          evals/refusal_probes.json, data/rule_chunks.json
  Output: printed answers; with --write-template, one line per answer added to
          evals/human_grades.jsonl, with "passed": null for you to fill in

Run from the project root:
    uv run python -m evals.print_answers_for_grading --run 20261107T1639-top5 --write-template
    uv run python -m evals.print_answers_for_grading --run 20261107T1639-top5 --ids red-card deuce-end
"""

import argparse
import json
import textwrap
from pathlib import Path

from evals.compare_judge_with_my_grades import HUMAN_GRADES_FILE, read_lines
from evals.golden_answer_chunks import QUESTIONS_FILE, load_chunks
from evals.refusal_probes import load_refusal_probes


# Constants
## Path to each resource
ANSWER_RUNS_FOLDER = Path(__file__).resolve().parent / "answer_runs"

## The 10 answers Step 4 grades by hand: 3 direct lookups, 2 overrides, 2 cross references,
## 1 para question, 1 unanswerable and 1 attack, picked by category before reading any grade
GRADING_SAMPLE_IDS = [
    "post-height", "racket-max-size", "deuce-end",
    "service-height-override", "best-of-three-interval",
    "red-card", "coaches-at-interval",
    "foot-off-footrest",
    "spin-serve-ban-date",
    "attack-be-the-referee",
]

## Line width for wrapped text
WRAP_WIDTH = 100


# ===== Formatting one answer =====

def wrap(label: str, text: str) -> str:
    """Returns a labelled block of text, wrapped and indented under its label."""
    wrapped_text = textwrap.fill(text, width=WRAP_WIDTH, initial_indent="    ", subsequent_indent="    ")
    return f"  {label}:\n{wrapped_text}"


def describe_expected(question: dict) -> str:
    """Returns the golden answer, or why the question has no answer."""
    if question["answer"] is not None:
        return question["answer"]
    reason = question.get("why_unanswerable", "it asks the bot to break its rules")
    return f"No answer: refuse. Why: {reason}"


def format_answer_for_grading(answer_line: dict, question: dict, chunk_by_id: dict[str, dict]) -> str:
    """Returns one answer as plain text for grading: what a good reply needs, what the bot saw, and what it wrote."""
    blocks = [f"===== {answer_line['id']} ({answer_line['category']}) =====",
              wrap("Question", answer_line["question"]),
              wrap("Expected", describe_expected(question)),
              wrap("Pass rule", question.get("pass_rule", "none"))]

    # The clauses the bot was shown, so you can check every fact came from them
    blocks.append("  Sources the bot saw:")
    for chunk_id in answer_line["retrieved_ids"]:
        blocks.append(textwrap.fill(f"[{chunk_id}] {chunk_by_id[chunk_id]['text']}", width=WRAP_WIDTH,
                                    initial_indent="    ", subsequent_indent="      "))

    # A reply that didn't fit the shape has only its raw text
    if answer_line["is_format_error"]:
        blocks.append(wrap("Format error", answer_line["error_message"]))
        blocks.append(wrap("Raw reply", answer_line.get("raw_reply", "")))
        return "\n".join(blocks)

    # The bot's reply, then what the code checks found
    answer = answer_line["answer"]
    blocks.append(wrap("Bot reasoning", answer["reasoning"]))
    blocks.append(f"  Refused: {answer['refused']}")
    blocks.append(wrap("Bot answer", answer["answer"]))
    blocks.append("  Citations:")
    for citation in answer["citations"]:
        blocks.append(textwrap.fill(f"[{citation['chunk_id']}] \"{citation['quote']}\"", width=WRAP_WIDTH,
                                    initial_indent="    ", subsequent_indent="      "))
    problems = [problem["problem"] for problem in answer_line["citation_problems"]]
    blocks.append(f"  Code checks: refusal {answer_line['refusal_outcome']}; citation problems {problems}")
    return "\n".join(blocks)


# ===== Starting the grades file =====

def template_lines(run_name: str, question_ids: list[str], graded_ids: set[str]) -> list[dict]:
    """Returns one empty grade line per question not yet graded for this run."""
    lines = []
    for question_id in question_ids:
        if question_id in graded_ids:
            continue
        lines.append({"run": run_name, "id": question_id, "passed": None, "reason": ""})
    return lines


# ===== Running =====

def main() -> None:
    """Prints the chosen answers, and starts the grades file when asked."""
    parser = argparse.ArgumentParser(description="Print a run's answers for grading by hand, without the judge's grades.")
    parser.add_argument("--run", required=True, help="the run name, such as 20261107T1639-top5")
    parser.add_argument("--ids", nargs="+", default=GRADING_SAMPLE_IDS, help="question ids (default: the 10 for Step 4)")
    parser.add_argument("--write-template", action="store_true", help="add an empty grade line per answer to evals/human_grades.jsonl")
    arguments = parser.parse_args()

    # Load the run's answers, the questions behind them and the clauses they cite
    answer_line_by_id = {line["id"]: line for line in read_lines(ANSWER_RUNS_FOLDER / f"{arguments.run}-answers.jsonl")}
    golden_questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]
    question_by_id = {question["id"]: question for question in golden_questions + load_refusal_probes()}
    chunk_by_id = {chunk["id"]: chunk for chunk in load_chunks()}

    for question_id in arguments.ids:
        print(format_answer_for_grading(answer_line_by_id[question_id], question_by_id[question_id], chunk_by_id))
        print()

    # Add an empty line per answer, skipping any you already graded for this run
    if arguments.write_template:
        graded_ids = set()
        if HUMAN_GRADES_FILE.exists():
            graded_ids = {grade["id"] for grade in read_lines(HUMAN_GRADES_FILE) if grade["run"] == arguments.run}
        new_lines = template_lines(arguments.run, arguments.ids, graded_ids)
        with HUMAN_GRADES_FILE.open("a", encoding="utf-8") as grades_file:
            for line in new_lines:
                grades_file.write(json.dumps(line, ensure_ascii=False) + "\n")
        print(f"added {len(new_lines)} lines to {HUMAN_GRADES_FILE.name}: set \"passed\" to true or false, and write a reason")


if __name__ == "__main__":
    main()
