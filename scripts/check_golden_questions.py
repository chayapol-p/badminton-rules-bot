"""
Checks the golden question set against the ingested clause chunks.

For every answer location in golden_questions.json, it finds the chunk that holds it,
with the same matcher the scorer uses (evals/golden.py). Any location with no chunk
means the ingest lost a clause, or the question cites the wrong place.

Run from the project root (after scripts.ingest_rules):
    uv run python -m scripts.check_golden_questions
"""

import json
from collections import Counter
from pathlib import Path

from evals.golden import expected_chunk_ids


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
QUESTIONS_FILE = PROJECT_FOLDER / "evals" / "golden_questions.json"
CHUNKS_FILE = PROJECT_FOLDER / "data" / "rule_chunks.json"


# ===== Load the questions and the chunks =====

golden_set = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))


# ===== Find the chunk for one answer location =====

def find_chunks(location):
    """Returns the ids of chunks that hold this location, with the matcher the scorer uses."""
    return expected_chunk_ids(location, chunks)


# ===== Check every location, then the spread of questions =====

missing_locations = []
for question in golden_set["questions"]:
    for location in question["answer_locations"]:
        if not find_chunks(location):
            missing_locations.append((question["id"], location["doc"], location["clause"]))

question_ids = [question["id"] for question in golden_set["questions"]]
print("questions:", len(question_ids), "| duplicate ids:", len(question_ids) - len(set(question_ids)))
print("missing locations:", missing_locations or "none")
print("by category:", dict(Counter(question["category"] for question in golden_set["questions"])))
print("by wording:", dict(Counter(question["wording"] for question in golden_set["questions"])))
