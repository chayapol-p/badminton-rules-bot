"""
Loads the golden questions for one split, and finds the chunks that hold each answer.

It uses the same matching rule as scripts/check_golden_questions.py, so the scorer and
the ingest check agree on what counts as the right chunk.
"""

import json
from pathlib import Path


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
QUESTIONS_FILE = PROJECT_FOLDER / "evals" / "golden_questions.json"
CHUNKS_FILE = PROJECT_FOLDER / "data" / "rule_chunks.json"


# ===== Loading =====

def load_chunks():
    """Returns every clause chunk from the ingest step."""
    return json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))


def load_questions(split_name):
    """Returns the golden questions in one split: "dev" or "held_out"."""
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]
    return [question for question in questions if question["split"] == split_name]


# ===== Matching an answer location to chunks =====

def expected_chunk_ids(location, chunks):
    """Returns the ids of chunks that hold one answer location (a document and a clause)."""
    # A location may name an Alternative Laws format ("variant"); then only that format counts
    same_document = [chunk for chunk in chunks if chunk["document"] == location["doc"]
                     and location.get("variant") in (None, chunk["variant"])]
    # Exact clause first, ignoring case, so "DIAGRAM A" finds the diagram chunk and nothing else
    by_clause = [chunk["id"] for chunk in same_document if chunk["clause"].lower() == location["clause"].lower()]
    if by_clause:
        return by_clause

    # Only labels such as "DIAGRAM A" or "In Force" may match by text. A clause number that
    # appears only inside another chunk's text means the ingest lost that clause
    if location["clause"][0].isdigit():
        return []
    label = location["clause"].lower()
    return [chunk["id"] for chunk in same_document if label in chunk["text"].lower()]
