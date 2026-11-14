"""
Checks the golden question set and the Phase 2 question set against the ingested clause chunks.

For every answer location in each set, it finds the chunk that holds it, with the same matcher the
scorer uses (evals/golden_answer_chunks.py). Any location with no chunk means the ingest lost a
clause, or the question cites the wrong place. It also flags a question id or text that appears in
both sets, so the Phase 2 runs never re-score a golden question.

Run from the project root (after scripts.build_rule_chunks):
    uv run python -m scripts.check_golden_questions
"""

import json
from collections import Counter
from pathlib import Path

from evals.golden_answer_chunks import expected_chunk_ids


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
QUESTION_FILES = {
    "golden": PROJECT_FOLDER / "evals" / "golden_questions.json",
    "phase2": PROJECT_FOLDER / "evals" / "phase2_questions.json",
}
CHUNKS_FILE = PROJECT_FOLDER / "data" / "rule_chunks.json"


# ===== One question set =====

def find_missing_locations(questions: list[dict], chunks: list[dict]) -> list[tuple[str, str, str]]:
    """Returns every answer location with no chunk that holds it, with the matcher the scorer uses."""
    missing_locations = []
    for question in questions:
        for location in question["answer_locations"]:
            if not expected_chunk_ids(location, chunks):
                missing_locations.append((question["id"], location["doc"], location["clause"]))
    return missing_locations


def print_set_check(set_name: str, questions: list[dict], chunks: list[dict]) -> None:
    """Prints one set's question count, duplicate ids, missing locations and spread of questions."""
    question_ids = [question["id"] for question in questions]
    print(f"{set_name} questions:", len(question_ids), "| duplicate ids:", len(question_ids) - len(set(question_ids)))
    print("missing locations:", find_missing_locations(questions, chunks) or "none")
    print("by category:", dict(Counter(question["category"] for question in questions)))
    print("by wording:", dict(Counter(question["wording"] for question in questions)))


# ===== Every set, then what the sets share =====

def main() -> None:
    """Checks each question set, then lists any id or question text that two sets share."""
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    questions_by_set = {}
    for set_name, questions_file in QUESTION_FILES.items():
        questions_by_set[set_name] = json.loads(questions_file.read_text(encoding="utf-8"))["questions"]
        print_set_check(set_name, questions_by_set[set_name], chunks)

    # A Phase 2 question must be new: the same id or the same wording would score a golden question twice
    golden_ids = {question["id"] for question in questions_by_set["golden"]}
    golden_texts = {question["question"].strip().lower() for question in questions_by_set["golden"]}
    shared = []
    for question in questions_by_set["phase2"]:
        is_shared = question["id"] in golden_ids or question["question"].strip().lower() in golden_texts
        if is_shared:
            shared.append(question["id"])
    print("in both sets:", shared or "none")


if __name__ == "__main__":
    main()
