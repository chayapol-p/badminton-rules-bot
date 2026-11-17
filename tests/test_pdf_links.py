"""
Slice 3 tests for the PDF links (spec criterion 3, record 0034): each citation in the answer event carries a link
that opens the frozen PDF at the clause's page, and FastAPI serves those PDFs at /rule-books.
Nothing here runs a paid API.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pdf_links import RULE_BOOKS_FOLDER, link_to_pdf_page
from evals.golden_answer_chunks import load_chunks
from tests.test_chat_endpoint import placeholder_keys, read_events  # placeholder_keys runs for every test here too


# Constants
ITTO_FILE_NAME = "bwf-itto-2025-v7.0.pdf"
ITTO_IS_MISSING = not (RULE_BOOKS_FOLDER / ITTO_FILE_NAME).exists()


# ===== The link for one clause =====

def test_a_clause_links_to_its_rule_book_at_its_page():
    # Record 0029 checked this page by hand: ITTO clause 7.2 is on page 37
    assert link_to_pdf_page("itto-7.2") == "/rule-books/bwf-itto-2025-v7.0.pdf#page=37"


def test_an_unknown_clause_fails_loudly():
    with pytest.raises(ValueError, match="laws-99.9"):
        link_to_pdf_page("laws-99.9")


# ===== The link in the answer event =====

def test_each_citation_in_the_answer_event_carries_its_pdf_link():
    chunk_by_id = {chunk["id"]: chunk for chunk in load_chunks()}
    posts_page = chunk_by_id["laws-1.4"]["page"]

    with TestClient(app) as client:
        response = client.post("/chat", json={"question": "How tall are the posts?"})

    answer_data = [event_data for event_name, event_data in read_events(response.text) if event_name == "answer"][0]
    citation = json.loads(answer_data)["citations"][0]
    assert citation["chunk_id"] == "laws-1.4"
    assert citation["pdf_link"] == f"/rule-books/bwf-laws-of-badminton-2025-v5.0.pdf#page={posts_page}"


# ===== The PDFs themselves =====

@pytest.mark.skipif(ITTO_IS_MISSING, reason="the rule-book PDFs in data/bwf/ are downloaded by hand and never committed")
def test_the_app_serves_the_rule_book_pdfs():
    with TestClient(app) as client:
        response = client.get(f"/rule-books/{ITTO_FILE_NAME}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
