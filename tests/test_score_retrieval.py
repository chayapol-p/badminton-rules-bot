"""
Tests the retrieval scorer on a small sample of the real data, where every right answer is known.

The sample is three real chunks and three real golden questions, copied as they are
(7 Nov 2026), so the tests run in a fresh clone before any ingest. The last test checks
that the copies still match the real files whenever those files exist.

The three search functions are stubs: each returns a fixed list of chunks, so the
scores they should get are known before the test runs.
"""

import json
from pathlib import Path

import pytest

from evals.score_retrieval import score_search


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
CHUNKS_FILE = PROJECT_FOLDER / "data" / "rule_chunks.json"
QUESTIONS_FILE = PROJECT_FOLDER / "evals" / "golden_questions.json"


# ===== A sample of the real data: three chunks and three questions =====

## Laws 7.4 and 7.5 answer the deuce question together; Law 1.4 answers the posts question
SAMPLE_CHUNKS = [
    {
        "id": "laws-7.4",
        "document": "laws",
        "document_title": "Laws of Badminton",
        "version": "5.0 (2)",
        "in_force": "2025-04-26",
        "clause": "7.4",
        "alternative_format": None,
        "heading": "7. SCORING SYSTEM",
        "para_only": False,
        "page": 5,
        "text": "If the score becomes 20-all, the side which gains a two point lead first, shall win that game.",
        "search_text": "Laws of Badminton · 7. SCORING SYSTEM · Clause 7.4\nIf the score becomes 20-all, the side which gains a two point lead first, shall win that game.",
    },
    {
        "id": "laws-7.5",
        "document": "laws",
        "document_title": "Laws of Badminton",
        "version": "5.0 (2)",
        "in_force": "2025-04-26",
        "clause": "7.5",
        "alternative_format": None,
        "heading": "7. SCORING SYSTEM",
        "para_only": False,
        "page": 5,
        "text": "If the score becomes 29-all, the side scoring the 30th point shall win that game.",
        "search_text": "Laws of Badminton · 7. SCORING SYSTEM · Clause 7.5\nIf the score becomes 29-all, the side scoring the 30th point shall win that game.",
    },
    {
        "id": "laws-1.4",
        "document": "laws",
        "document_title": "Laws of Badminton",
        "version": "5.0 (2)",
        "in_force": "2025-04-26",
        "clause": "1.4",
        "alternative_format": None,
        "heading": "1. COURT AND COURT EQUIPMENT",
        "para_only": False,
        "page": 1,
        "text": "The posts shall be 1.55 metres in height from the surface of the court and shall remain vertical when the net is strained as provided in Law 1.10.",
        "search_text": "Laws of Badminton · 1. COURT AND COURT EQUIPMENT · Clause 1.4\nThe posts shall be 1.55 metres in height from the surface of the court and shall remain vertical when the net is strained as provided in Law 1.10.",
    },
]

## Two answerable questions (one needs 2 clauses, one needs 1) and one with no answer
SAMPLE_QUESTIONS = [
    {
        "id": "deuce-end",
        "category": "direct_lookup",
        "wording": "paraphrased",
        "question": "We're tied 20-20. When does the game actually end?",
        "answer": "The first side to get a two-point lead wins. If it reaches 29-all, the side that scores the 30th point wins.",
        "answer_locations": [{"doc": "laws", "clause": "7.4"}, {"doc": "laws", "clause": "7.5"}],
        "split": "dev",
    },
    {
        "id": "post-height",
        "category": "direct_lookup",
        "wording": "exact_term",
        "question": "How tall are the posts that hold the net?",
        "answer": "1.55 metres from the surface of the court, and they must stay vertical when the net is strained.",
        "answer_locations": [{"doc": "laws", "clause": "1.4"}],
        "split": "dev",
    },
    {
        "id": "ceiling-height",
        "category": "unanswerable",
        "kind": "missing_field",
        "wording": "paraphrased",
        "question": "What is the minimum ceiling height for a badminton hall?",
        "answer": None,
        "answer_locations": [],
        "why_unanswerable": "Law 13.3.3 makes touching the ceiling a fault, and a note allows local bye-laws for obstructions, but no height is given.",
        "pass_rule": "Gives no number. May say touching the ceiling is a fault (Law 13.3.3).",
        "split": "dev",
    },
]


# ===== Stub searches with known results =====

def perfect_search(question_text, top_k):
    """Stub: returns every sample chunk, so every answer location is found."""
    return SAMPLE_CHUNKS[:top_k]

def empty_search(question_text, top_k):
    """Stub: returns nothing, so no answer location is found."""
    return []

def half_search(question_text, top_k):
    """Stub: returns only Law 7.5, so the deuce question finds 1 of its 2 locations."""
    return [SAMPLE_CHUNKS[1]]


# ===== Tests =====

def test_perfect_search_scores_full_marks():
    """A perfect search scores 1.0 on both numbers."""
    scores = score_search(perfect_search, SAMPLE_QUESTIONS, SAMPLE_CHUNKS, top_k=5)
    assert scores["recall_at_5"] == 1.0
    assert scores["hit_at_5"] == 1.0

def test_empty_search_scores_zero():
    """An empty search scores 0.0 on both numbers."""
    scores = score_search(empty_search, SAMPLE_QUESTIONS, SAMPLE_CHUNKS, top_k=5)
    assert scores["recall_at_5"] == 0.0
    assert scores["hit_at_5"] == 0.0

def test_unanswerable_questions_are_not_scored():
    """Only the 2 answerable questions are scored: the ceiling question is skipped."""
    scores = score_search(perfect_search, SAMPLE_QUESTIONS, SAMPLE_CHUNKS, top_k=5)
    assert scores["questions_scored"] == 2

def test_partial_find_counts_for_hit_but_halves_recall():
    """Deuce finds 1 of 2 locations and posts finds none: recall (0.5 + 0) / 2, hit 1 / 2."""
    scores = score_search(half_search, SAMPLE_QUESTIONS, SAMPLE_CHUNKS, top_k=5)
    assert scores["recall_at_5"] == 0.25
    assert scores["hit_at_5"] == 0.5


# ===== The sample stays a true copy of the real data =====

def test_sample_matches_the_real_files():
    """Each sample record equals its record in the real files, so the sample never drifts."""
    if not CHUNKS_FILE.exists():
        pytest.skip("data/rule_chunks.json is missing: run scripts.build_rule_chunks first")
    real_chunks_by_id = {chunk["id"]: chunk for chunk in json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))}
    real_questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["questions"]
    real_questions_by_id = {question["id"]: question for question in real_questions}

    for chunk in SAMPLE_CHUNKS:
        assert chunk == real_chunks_by_id[chunk["id"]]
    for question in SAMPLE_QUESTIONS:
        assert question == real_questions_by_id[question["id"]]
