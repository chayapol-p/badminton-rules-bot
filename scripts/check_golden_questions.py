"""
Checks the golden question set against the ingested clause chunks.

For every answer location in golden_questions.json, it finds the chunk that holds it:
a chunk with the same document and clause number, or (for labels like "DIAGRAM A" or
"In Force") a chunk of that document whose text contains the label. Any location with
no chunk means the ingest lost a clause, or the question cites the wrong place.

Run from the project root (after scripts.ingest_rules):
    uv run python -m scripts.check_golden_questions
"""

import json
from collections import Counter
from pathlib import Path


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
    """Returns the ids of chunks that hold this document and clause."""
    same_document = [chunk for chunk in chunks if chunk["document"] == location["doc"]]
    by_clause = [chunk["id"] for chunk in same_document if chunk["clause"] == location["clause"]]
    if by_clause:
        return by_clause

    # Only labels such as "DIAGRAM A" or "In Force" may match by text. A clause number that
    # appears only inside another chunk's text means the ingest lost that clause
    if location["clause"][0].isdigit():
        return []
    label = location["clause"].lower()
    return [chunk["id"] for chunk in same_document if label in chunk["text"].lower()]


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
