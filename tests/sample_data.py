"""
A small sample of the real data, shared by the search and scorer tests.

Three real chunks and three real golden questions, copied as they are (7 Nov 2026), so the
tests run in a fresh clone before any ingest. tests/test_score_retrieval.py checks that the
copies still match the real files whenever those files exist.
"""


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
