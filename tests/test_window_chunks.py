"""
Tests the fixed-size windows: right size, every clause covered, no window across two documents.
"""

import pytest

from evals.golden_answer_chunks import CHUNKS_FILE, load_chunks
from retrieval.window_chunks import WINDOW_CHARACTERS, build_windows


# ===== Build the windows once from the real chunks =====

@pytest.fixture(scope="module")
def chunks_and_windows():
    """The real clause chunks and the windows cut from them."""
    if not CHUNKS_FILE.exists():
        pytest.skip("data/rule_chunks.json is missing: run scripts.build_rule_chunks first")
    chunks = load_chunks()
    return chunks, build_windows(chunks)


# ===== Tests =====

def test_no_window_is_longer_than_the_window_size(chunks_and_windows):
    _, windows = chunks_and_windows
    too_long = [window["id"] for window in windows if len(window["text"]) > WINDOW_CHARACTERS]
    assert too_long == []


def test_every_clause_is_covered_by_a_window(chunks_and_windows):
    chunks, windows = chunks_and_windows
    covered_ids = set()
    for window in windows:
        covered_ids.update(window["covers"])
    uncovered = [chunk["id"] for chunk in chunks if chunk["id"] not in covered_ids]
    assert uncovered == []


def test_a_window_covers_clauses_of_its_own_document_only(chunks_and_windows):
    chunks, windows = chunks_and_windows
    document_by_id = {chunk["id"]: chunk["document"] for chunk in chunks}
    crossing = []
    for window in windows:
        for clause_id in window["covers"]:
            if document_by_id[clause_id] != window["document"]:
                crossing.append(window["id"])
    assert crossing == []


def test_window_ids_are_unique(chunks_and_windows):
    _, windows = chunks_and_windows
    window_ids = [window["id"] for window in windows]
    assert len(window_ids) == len(set(window_ids))


def test_a_known_clause_sits_in_a_window_with_its_number(chunks_and_windows):
    """Law 1.4 keeps its number in the window text, as the PDF prints it."""
    _, windows = chunks_and_windows
    windows_with_posts = [window for window in windows if "laws-1.4" in window["covers"]]
    assert windows_with_posts
    assert "1.4 The posts shall be 1.55 metres" in windows_with_posts[0]["text"]
