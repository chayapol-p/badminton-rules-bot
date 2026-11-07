"""
Tests keyword search on the sample chunks: clause numbers stay whole, and the right clause ranks first.
"""

from retrieval.keyword_search import KeywordSearch, tokenize
from tests.sample_data import SAMPLE_CHUNKS


# ===== Turning text into words =====

def test_tokenize_lowercases_and_keeps_clause_numbers_whole():
    assert tokenize("Law 9.1.6 says: Serve!") == ["law", "9.1.6", "says", "serve"]


# ===== Ranking =====

def test_the_clause_with_the_question_words_ranks_first():
    keyword_search = KeywordSearch(SAMPLE_CHUNKS)
    results = keyword_search.search("How tall are the posts?", top_k=1)
    assert [chunk["id"] for chunk in results] == ["laws-1.4"]


def test_a_rare_word_decides_between_two_close_clauses():
    """"29" appears only in Law 7.5, while "all" appears in both 7.4 and 7.5."""
    keyword_search = KeywordSearch(SAMPLE_CHUNKS)
    results = keyword_search.search("tied at 29-all", top_k=1)
    assert [chunk["id"] for chunk in results] == ["laws-7.5"]


def test_search_returns_top_k_chunks():
    keyword_search = KeywordSearch(SAMPLE_CHUNKS)
    assert len(keyword_search.search("game", top_k=2)) == 2


def test_a_question_with_no_shared_words_still_returns_top_k_chunks():
    """No shared words gives every chunk a score of 0, but search still returns top_k chunks."""
    keyword_search = KeywordSearch(SAMPLE_CHUNKS)
    results = keyword_search.search("shuttlecock feathers", top_k=3)
    assert len(results) == 3
