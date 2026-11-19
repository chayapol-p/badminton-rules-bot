"""
Checks the golden question set and the Phase 2 question set against the ingested clause chunks.

For every answer location in each set, it finds the chunk that holds it, with the same matcher the
scorer uses (evals/golden_answer_chunks.py). Any location with no chunk means the ingest lost a
clause, or the question cites the wrong place. It also flags a question id or text that appears in
both sets, so the Phase 2 runs never re-score a golden question.

  Input:  evals/golden_questions.json, evals/phase2_questions.json, data/rule_chunks.json
  Output: printed counts and problems for each set, then the questions both sets share

Run from the project root (after scripts.build_rule_chunks):
    uv run python -m scripts.check_golden_questions
"""

import json
from collections import Counter
from pathlib import Path

from evals.golden_answer_chunks import QUESTIONS_FILE, expected_chunk_ids
from retrieval.load_rule_chunks import load_chunks


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
QUESTION_FILES = {
    "golden": QUESTIONS_FILE,
    "phase2": PROJECT_FOLDER / "evals" / "phase2_questions.json",
}


# ===== One question set =====

def find_missing_locations(questions: list[dict], chunks: list[dict]) -> list[tuple[str, str, str]]:
    """Returns every answer location with no chunk that holds it, with the matcher the scorer uses."""
    missing_locations = []
    for question in questions:
        for location in question["answer_locations"]:
            if not expected_chunk_ids(location, chunks):
                missing_locations.append((question["id"], location["doc"], location["clause"]))
    return missing_locations


def describe_list(items: list) -> str:
    """Returns the list as text, or "none" when it is empty."""
    if items:
        return str(items)
    return "none"


def print_set_check(set_name: str, questions: list[dict], chunks: list[dict]) -> None:
    """Prints one set's question count, duplicate ids, missing locations and spread of questions."""
    question_ids = [question["id"] for question in questions]
    duplicate_id_count = len(question_ids) - len(set(question_ids))
    print(f"{set_name} questions:", len(question_ids), "| duplicate ids:", duplicate_id_count)
    print("missing locations:", describe_list(find_missing_locations(questions, chunks)))
    print("by category:", dict(Counter(question["category"] for question in questions)))
    print("by wording:", dict(Counter(question["wording"] for question in questions)))


# ===== What two sets share =====

def normalise_question_text(question: dict) -> str:
    """Returns the question's wording without case or outer spaces, so a copied question still matches."""
    return question["question"].strip().lower()


def find_shared_question_ids(new_questions: list[dict], golden_questions: list[dict]) -> list[str]:
    """Returns the ids of new questions whose id or wording is already a golden question."""
    golden_ids = {question["id"] for question in golden_questions}
    golden_texts = {normalise_question_text(question) for question in golden_questions}

    shared_question_ids = []
    for question in new_questions:
        if question["id"] in golden_ids:
            shared_question_ids.append(question["id"])
        elif normalise_question_text(question) in golden_texts:
            shared_question_ids.append(question["id"])
    return shared_question_ids


# ===== Every set, then what the sets share =====

def main() -> None:
    """Checks each question set, then lists any id or question text that two sets share."""

    # Check each set against the chunks
    chunks = load_chunks()
    questions_by_set = {}
    for set_name, questions_file in QUESTION_FILES.items():
        questions_by_set[set_name] = json.loads(questions_file.read_text(encoding="utf-8"))["questions"]
        print_set_check(set_name, questions_by_set[set_name], chunks)

    # A Phase 2 question must be new: the same id or the same wording would score a golden question twice
    shared_question_ids = find_shared_question_ids(questions_by_set["phase2"], questions_by_set["golden"])
    print("in both sets:", describe_list(shared_question_ids))


if __name__ == "__main__":
    main()
