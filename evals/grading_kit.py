"""
The grading kit: lets the code checks fail what they can, then prints the rest for grading by hand, without the judge's grades.

Step 1, code checks. An answer with a format error, a wrong refusal (missed or false) or a
citation problem has already failed. These are listed first and are not graded by hand.

Step 2, grading by hand. The kit takes the 10 Step 4 answers and swaps any answer the code
checks failed for the next clean answer in the same category, so your grades test the judge on
the part only it can grade: are the key facts right, is every fact in the sources, is the pass
rule followed. For each answer it prints, in this order: the code checks, the bot's answer, the
question with its golden answer and pass rule, then each citation with the clause it quotes.

  Input:  evals/answer_runs/<run>-answers.jsonl, evals/golden_questions.json,
          evals/refusal_probes.json, data/rule_chunks.json
  Output: printed kit; with --write-template, one "passed": null line per answer still to grade
          in evals/human_grades.jsonl (graded lines are never touched)

Run from the project root:
    uv run python -m evals.grading_kit --run 20261107T1639-top5 --write-template
"""

import argparse
import json
import textwrap
from pathlib import Path

from answer.check_refusals import FALSE_REFUSAL, MISSED_REFUSAL
from evals.compare_judge_with_my_grades import HUMAN_GRADES_FILE, read_lines
from evals.golden_answer_chunks import QUESTIONS_FILE, load_chunks
from evals.refusal_probes import load_refusal_probes
from experiments.compare_answer_setups import IMAGE_ONLY_QUESTION_IDS


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

## Refusal outcomes the code already counts as a fail
WRONG_REFUSALS = {MISSED_REFUSAL, FALSE_REFUSAL}

## Line width for wrapped text
WRAP_WIDTH = 100


# ===== Step 1: what the code checks already failed =====

def code_check_failures(answer_line: dict) -> list[str]:
    """Returns what the code checks failed for one answer: a format error, a wrong refusal, or each citation problem."""
    if answer_line["is_format_error"]:
        return ["format error"]

    failures = []
    if answer_line["refusal_outcome"] in WRONG_REFUSALS:
        failures.append(answer_line["refusal_outcome"])
    for problem in answer_line["citation_problems"]:
        failures.append(f"citation [{problem['chunk_id']}] {problem['problem']}")
    return failures


# ===== Step 2: which answers to grade by hand =====

def pick_grading_sample(answer_lines: list[dict], preferred_ids: list[str]) -> tuple[list[dict], list[str]]:
    """Returns the answers to grade, swapping any the code checks failed for the next clean answer in the same category, plus a note per swap."""
    answer_line_by_id = {line["id"]: line for line in answer_lines}
    picked_ids = set()
    sample = []
    swap_notes = []

    for preferred_id in preferred_ids:
        preferred_line = answer_line_by_id[preferred_id]
        if not code_check_failures(preferred_line):
            sample.append(preferred_line)
            picked_ids.add(preferred_id)
            continue

        # Take the first clean answer in the same category that isn't picked or planned already
        for line in answer_lines:
            is_same_category = line["category"] == preferred_line["category"]
            is_free = line["id"] not in picked_ids and line["id"] not in preferred_ids
            if is_same_category and is_free and not code_check_failures(line):
                sample.append(line)
                picked_ids.add(line["id"])
                swap_notes.append(f"{preferred_id} failed the code checks; {line['id']} takes its place")
                break
    return sample, swap_notes


# ===== Printing one answer =====

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
    """Returns one answer as plain text: code checks, the bot's answer, the question and what it needs, then each citation with its clause."""
    answer = answer_line["answer"]
    blocks = [f"===== {answer_line['id']} ({answer_line['category']}) =====",
              f"  Code checks: citations clean · refusal: {answer_line['refusal_outcome']}",
              wrap(f"Bot answer (refused: {answer['refused']})", answer["answer"]),
              wrap("Question", answer_line["question"]),
              wrap("Expected", describe_expected(question)),
              wrap("Pass rule", question.get("pass_rule", "none"))]

    # Each citation, with the clause it quotes, so you can see the fact came from it
    blocks.append("  Citations:")
    for citation in answer["citations"]:
        blocks.append(textwrap.fill(f"[{citation['chunk_id']}] \"{citation['quote']}\"", width=WRAP_WIDTH,
                                    initial_indent="    ", subsequent_indent="      "))
        blocks.append(textwrap.fill(f"clause: {chunk_by_id[citation['chunk_id']]['text']}", width=WRAP_WIDTH,
                                    initial_indent="      ", subsequent_indent="        "))

    # The other clauses the bot was shown, by id: any fact in its answer must come from one of these
    cited_ids = {citation["chunk_id"] for citation in answer["citations"]}
    uncited_ids = [chunk_id for chunk_id in answer_line["retrieved_ids"] if chunk_id not in cited_ids]
    blocks.append(f"  Also shown, not cited: {', '.join(uncited_ids)}")
    return "\n".join(blocks)


# ===== Starting the grades file =====

def template_lines(run_name: str, question_ids: list[str], graded_ids: set[str]) -> list[dict]:
    """Returns one empty grade line per question not yet in the grades file for this run."""
    lines = []
    for question_id in question_ids:
        if question_id in graded_ids:
            continue
        lines.append({"run": run_name, "id": question_id, "passed": None, "reason": ""})
    return lines


def refresh_grades_file(run_name: str, sample_ids: list[str]) -> int:
    """Drops this run's empty lines for answers no longer in the sample, adds empty lines for new ones, and returns how many it added."""
    existing_lines = []
    if HUMAN_GRADES_FILE.exists():
        existing_lines = read_lines(HUMAN_GRADES_FILE)

    # Keep every graded line, and every line from other runs; drop only this run's empty lines that left the sample
    kept_lines = []
    for line in existing_lines:
        is_empty_line_of_this_run = line["run"] == run_name and line["passed"] is None
        if is_empty_line_of_this_run and line["id"] not in sample_ids:
            continue
        kept_lines.append(line)

    present_ids = {line["id"] for line in kept_lines if line["run"] == run_name}
    new_lines = template_lines(run_name, sample_ids, present_ids)
    with HUMAN_GRADES_FILE.open("w", encoding="utf-8") as grades_file:
        for line in kept_lines + new_lines:
            grades_file.write(json.dumps(line, ensure_ascii=False) + "\n")
    return len(new_lines)


# ===== Running =====

def main() -> None:
    """Prints the code-check failures, then the answers to grade by hand, and refreshes the grades file when asked."""
    parser = argparse.ArgumentParser(description="Grading kit: code-check failures first, then answers to grade by hand.")
    parser.add_argument("--run", required=True, help="the run name, such as 20261107T1639-top5")
    parser.add_argument("--write-template", action="store_true", help="add an empty grade line per answer still to grade")
    arguments = parser.parse_args()

    # Load the run's answers, the questions behind them and the clauses they cite
    answer_lines = read_lines(ANSWER_RUNS_FOLDER / f"{arguments.run}-answers.jsonl")
    golden_questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]
    question_by_id = {question["id"]: question for question in golden_questions + load_refusal_probes()}
    chunk_by_id = {chunk["id"]: chunk for chunk in load_chunks()}

    # Step 1: what the code checks already failed, across the whole run
    print("===== Step 1: failed by the code checks (no need to grade) =====")
    for line in answer_lines:
        failures = code_check_failures(line)
        if not failures:
            continue

        # Refusing an image-only question is fair until images arrive, so say so
        note = ""
        if line["id"] in IMAGE_ONLY_QUESTION_IDS:
            note = " (image-only: refusing is fair until Week 4, and the scores leave it out)"
        print(f"  {line['id']}: {'; '.join(failures)}{note}")

    # Step 2: the answers to grade by hand
    sample, swap_notes = pick_grading_sample(answer_lines, GRADING_SAMPLE_IDS)
    print("\n===== Step 2: grade these by hand =====")
    for note in swap_notes:
        print(f"  note: {note}")
    for line in sample:
        print()
        print(format_answer_for_grading(line, question_by_id[line["id"]], chunk_by_id))

    if arguments.write_template:
        added_count = refresh_grades_file(arguments.run, [line["id"] for line in sample])
        print(f"\nadded {added_count} lines to {HUMAN_GRADES_FILE.name}: set \"passed\" to true or false, and write a reason")


if __name__ == "__main__":
    main()
