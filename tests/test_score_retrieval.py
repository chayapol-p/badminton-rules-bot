"""
Tests the retrieval scorer on a tiny made-up corpus, so a scorer bug can't hide behind real data.
"""

from evals.score_retrieval import score_search


# ===== A tiny corpus and three questions =====

FAKE_CHUNKS = [
    {"id": "laws-7.4", "document": "laws", "clause": "7.4", "text": "two-point lead"},
    {"id": "laws-7.5", "document": "laws", "clause": "7.5", "text": "29-all"},
    {"id": "laws-1.4", "document": "laws", "clause": "1.4", "text": "1.55 metres"},
]

FAKE_QUESTIONS = [
    {"id": "deuce", "category": "direct_lookup", "question": "tied 20-20?", "answer": "x",
     "answer_locations": [{"doc": "laws", "clause": "7.4"}, {"doc": "laws", "clause": "7.5"}]},
    {"id": "posts", "category": "direct_lookup", "question": "post height?", "answer": "x",
     "answer_locations": [{"doc": "laws", "clause": "1.4"}]},
    {"id": "ceiling", "category": "unanswerable", "question": "ceiling height?", "answer": None,
     "answer_locations": []},
]


# ===== Search functions with known results =====

def perfect_search(question_text, top_k):
    """Returns every chunk, so every answer location is found."""
    return FAKE_CHUNKS[:top_k]

def empty_search(question_text, top_k):
    """Returns nothing, so no answer location is found."""
    return []

def half_search(question_text, top_k):
    """Returns only clause 7.5, so the deuce question finds 1 of its 2 locations."""
    return [FAKE_CHUNKS[1]]


# ===== Tests =====

def test_perfect_search_scores_full_marks():
    """A perfect search scores 1.0 on both numbers."""
    scores = score_search(perfect_search, FAKE_QUESTIONS, FAKE_CHUNKS, top_k=5)
    assert scores["recall_at_5"] == 1.0
    assert scores["hit_at_5"] == 1.0

def test_empty_search_scores_zero():
    """An empty search scores 0.0 on both numbers."""
    scores = score_search(empty_search, FAKE_QUESTIONS, FAKE_CHUNKS, top_k=5)
    assert scores["recall_at_5"] == 0.0
    assert scores["hit_at_5"] == 0.0

def test_unanswerable_questions_are_not_scored():
    """Only the 2 answerable questions are scored: the unanswerable one is skipped."""
    scores = score_search(perfect_search, FAKE_QUESTIONS, FAKE_CHUNKS, top_k=5)
    assert scores["questions_scored"] == 2

def test_partial_find_counts_for_hit_but_halves_recall():
    """Deuce finds 1 of 2 locations and posts finds none: recall (0.5 + 0) / 2, hit 1 / 2."""
    scores = score_search(half_search, FAKE_QUESTIONS, FAKE_CHUNKS, top_k=5)
    assert scores["recall_at_5"] == 0.25
    assert scores["hit_at_5"] == 0.5
