"""
Hybrid search: merges the keyword ranking and the vector ranking with reciprocal rank fusion.

Each search gives its own ranking, and their scores can't be compared (a BM25 score of 12
and a cosine of 0.8 mean different things). Reciprocal rank fusion uses only the ranks: a
chunk earns 1 / (60 + rank) from every list it appears in, and the totals decide the order.
A chunk near the top of both lists beats a chunk at the top of only one.

The constant 60 comes from Cormack, Clarke and Buettcher (SIGIR 2009), and is the usual default.

Use:
    hybrid_search = HybridSearch(keyword_search, vector_search)
    results = hybrid_search.search("How tall are the posts?", top_k=5)
"""

from collections import defaultdict


# Constants
## The rank fusion constant: a larger value flattens the gap between rank 1 and rank 10
RANK_FUSION_CONSTANT = 60

## How many results each search hands to the fusion before the top_k cut
CANDIDATE_COUNT = 20


# ===== Merging rankings =====

def reciprocal_rank_fusion(rankings, constant=RANK_FUSION_CONSTANT):
    """Merges ranked lists of chunks into one list, ordered by the sum of 1 / (constant + rank)."""
    fused_score_by_id = defaultdict(float)
    chunk_by_id = {}

    # Every list adds a score to each chunk it holds, by that chunk's rank in the list
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            fused_score_by_id[chunk["id"]] += 1/(constant + rank)
            chunk_by_id[chunk["id"]] = chunk

    # Highest total first; sorted() is stable, so ties keep the order chunks were first seen
    ranked_ids = sorted(fused_score_by_id, key=fused_score_by_id.get, reverse=True)
    return [chunk_by_id[chunk_id] for chunk_id in ranked_ids]


# ===== The search =====

class HybridSearch:
    """Runs a keyword search and a vector search, then fuses their rankings."""

    def __init__(self, keyword_search, vector_search, candidate_count=CANDIDATE_COUNT):
        self.keyword_search = keyword_search
        self.vector_search = vector_search
        self.candidate_count = candidate_count

    def search(self, question_text, top_k):
        """Returns the top_k chunks after fusing the two rankings."""
        # Each search returns more candidates than needed, so the fusion has room to reorder
        keyword_ranking = self.keyword_search.search(question_text, self.candidate_count)
        vector_ranking = self.vector_search.search(question_text, self.candidate_count)

        fused_ranking = reciprocal_rank_fusion([keyword_ranking, vector_ranking])
        return fused_ranking[:top_k]
