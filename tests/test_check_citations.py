"""
Tests the citation check on real clauses from the sample data, with answers written by hand.
"""

import json

import pytest

from answer.answer_shape import Citation, RulesAnswer
from answer.check_citations import find_citation_problem, find_citation_problems
from evals.golden_answer_chunks import CHUNKS_FILE
from tests.sample_data import SAMPLE_CHUNKS


# ===== The chunks the model was shown: Laws 7.4 and 7.5, not 1.4 =====

RETRIEVED_CHUNKS = SAMPLE_CHUNKS[:2]

## Law 9.1.6, copied as it is (7 Nov 2026): the rule books print a curly apostrophe in "server’s"
SERVICE_HEIGHT_CHUNK = {
    "id": "laws-9.1.6",
    "document": "laws",
    "document_title": "Laws of Badminton",
    "version": "5.0 (2)",
    "in_force": "2025-04-26",
    "clause": "9.1.6",
    "alternative_format": None,
    "heading": "9. SERVICE",
    "para_only": False,
    "page": 6,
    "text": "the whole shuttle shall be below 1.15 metres from the surface of the court at the instant of being hit by the server’s racket;",
    "search_text": "Laws of Badminton · 9. SERVICE · Clause 9.1.6\nthe whole shuttle shall be below 1.15 metres from the surface of the court at the instant of being hit by the server’s racket;",
    "search_text_with_parents": "Laws of Badminton · 9. SERVICE · Clause 9.1.6\n9.1 In a correct service, the flight of the shuttle shall be upwards from the server’s\nthe whole shuttle shall be below 1.15 metres from the surface of the court at the instant of being hit by the server’s racket;"
}


# ===== One citation =====

def test_an_exact_quote_from_a_retrieved_clause_passes():
    citation = Citation(chunk_id="laws-7.5", quote="the side scoring the 30th point shall win that game")
    assert find_citation_problem(citation, RETRIEVED_CHUNKS) is None


def test_case_and_spacing_do_not_fail_a_true_quote():
    citation = Citation(chunk_id="laws-7.4", quote="If the score  becomes 20-ALL")
    assert find_citation_problem(citation, RETRIEVED_CHUNKS) is None


def test_a_straight_apostrophe_matches_the_rule_book_s_curly_one():
    """The rule books print "server’s"; a model usually types "server's"."""
    citation = Citation(chunk_id="laws-9.1.6", quote="at the instant of being hit by the server's racket")
    assert find_citation_problem(citation, [SERVICE_HEIGHT_CHUNK]) is None


def test_a_clause_the_model_never_saw_fails():
    citation = Citation(chunk_id="laws-1.4", quote="The posts shall be 1.55 metres in height")
    assert find_citation_problem(citation, RETRIEVED_CHUNKS) == "not retrieved"


def test_a_paraphrased_quote_fails():
    citation = Citation(chunk_id="laws-7.4", quote="the first side two points ahead wins")
    assert find_citation_problem(citation, RETRIEVED_CHUNKS) == "quote not in clause"


def test_an_empty_quote_fails():
    citation = Citation(chunk_id="laws-7.4", quote="  ")
    assert find_citation_problem(citation, RETRIEVED_CHUNKS) == "empty quote"


# ===== A whole answer =====

def test_an_answer_with_no_citation_fails():
    rules_answer = RulesAnswer(reasoning="Law 7.4 covers it.", refused=False, answer="Two points clear wins.", citations=[])
    assert find_citation_problems(rules_answer, RETRIEVED_CHUNKS) == [{"chunk_id": None, "problem": "no citation"}]


def test_a_refusal_may_cite_nothing():
    rules_answer = RulesAnswer(reasoning="No source covers it.", refused=True, answer="The sources don't say.", citations=[])
    assert find_citation_problems(rules_answer, RETRIEVED_CHUNKS) == []


def test_every_failed_citation_is_listed():
    citations = [
        Citation(chunk_id="laws-7.4", quote="If the score becomes 20-all"),
        Citation(chunk_id="laws-1.4", quote="1.55 metres"),
        Citation(chunk_id="laws-7.5", quote="30 points wins"),
    ]
    rules_answer = RulesAnswer(reasoning="Laws 7.4 and 7.5 cover it.", refused=False, answer="...", citations=citations)
    assert find_citation_problems(rules_answer, RETRIEVED_CHUNKS) == [
        {"chunk_id": "laws-1.4", "problem": "not retrieved", "quote": "1.55 metres"},
        {
            "chunk_id": "laws-7.5",
            "problem": "quote not in clause",
            "quote": "30 points wins",
            "clause_text": "If the score becomes 29-all, the side scoring the 30th point shall win that game.",
        },
    ]


# ===== The extra sample stays a true copy of the real data =====

def test_service_height_sample_matches_the_real_file():
    if not CHUNKS_FILE.exists():
        pytest.skip("data/rule_chunks.json is missing: run scripts.build_rule_chunks first")
    real_chunks_by_id = {chunk["id"]: chunk for chunk in json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))}
    assert SERVICE_HEIGHT_CHUNK == real_chunks_by_id["laws-9.1.6"]
