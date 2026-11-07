"""
Tests reciprocal rank fusion with rankings whose fused order can be worked out by hand.
"""

from retrieval.hybrid_search import HybridSearch, reciprocal_rank_fusion
from tests.sample_data import SAMPLE_CHUNKS


# ===== The sample chunks by name =====

DEUCE_RULE, EXTENSION_RULE, POST_RULE = SAMPLE_CHUNKS


class StubSearch:
    """Stub: returns the same ranking for any question."""

    def __init__(self, ranking):
        self.ranking = ranking

    def search(self, question_text, top_k):
        return self.ranking[:top_k]


# ===== Rank fusion =====

def test_a_chunk_high_in_both_lists_wins():
    """7.4 is 1st and 2nd: 1/61 + 1/62. 1.4 is 3rd and 1st: 1/63 + 1/61. 7.5 is 2nd and 3rd: 1/62 + 1/63."""
    keyword_ranking = [DEUCE_RULE, EXTENSION_RULE, POST_RULE]
    vector_ranking = [POST_RULE, DEUCE_RULE, EXTENSION_RULE]
    fused = reciprocal_rank_fusion([keyword_ranking, vector_ranking])
    assert [chunk["id"] for chunk in fused] == ["laws-7.4", "laws-1.4", "laws-7.5"]


def test_a_chunk_in_only_one_list_is_kept():
    fused = reciprocal_rank_fusion([[DEUCE_RULE], [POST_RULE]])
    assert {chunk["id"] for chunk in fused} == {"laws-7.4", "laws-1.4"}


def test_each_chunk_appears_once():
    fused = reciprocal_rank_fusion([[DEUCE_RULE, POST_RULE], [POST_RULE, DEUCE_RULE]])
    assert len(fused) == 2


# ===== The hybrid search =====

def test_hybrid_search_fuses_both_searches_and_cuts_to_top_k():
    keyword_search = StubSearch([DEUCE_RULE, EXTENSION_RULE, POST_RULE])
    vector_search = StubSearch([POST_RULE, DEUCE_RULE, EXTENSION_RULE])
    hybrid_search = HybridSearch(keyword_search, vector_search)
    results = hybrid_search.search("any question", top_k=2)
    assert [chunk["id"] for chunk in results] == ["laws-7.4", "laws-1.4"]
