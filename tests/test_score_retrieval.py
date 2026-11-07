"""
Tests the retrieval scorer on a small sample of the real data, where every right answer is known.

The sample lives in tests/sample_data.py. The last test checks that it still matches the
real files whenever those files exist.

The search functions are stubs: each returns a fixed list, so the scores they should get
are known before the test runs.
"""

import json
from pathlib import Path

import pytest

from evals.score_retrieval import score_search
from retrieval.window_chunks import build_windows
from tests.sample_data import SAMPLE_CHUNKS, SAMPLE_QUESTIONS


# Constants
## Path to each resource
PROJECT_FOLDER = Path(__file__).resolve().parent.parent
CHUNKS_FILE = PROJECT_FOLDER / "data" / "rule_chunks.json"
QUESTIONS_FILE = PROJECT_FOLDER / "evals" / "golden_questions.json"


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

def window_search(question_text, top_k):
    """Stub: returns the one window built from the sample chunks, which covers all three clauses."""
    return build_windows(SAMPLE_CHUNKS)[:top_k]


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


def test_a_window_counts_through_the_clauses_it_covers():
    """One window covers Laws 7.4, 7.5 and 1.4, so both answerable questions find every location."""
    scores = score_search(window_search, SAMPLE_QUESTIONS, SAMPLE_CHUNKS, top_k=5)
    assert scores["recall_at_5"] == 1.0


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
