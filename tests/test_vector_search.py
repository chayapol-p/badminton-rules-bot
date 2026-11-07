"""
Tests vector search with hand-picked vectors, so the right ranking is known without calling the API.
"""

import numpy

from retrieval.vector_search import VectorSearch
from tests.sample_data import SAMPLE_CHUNKS


# ===== One direction per sample chunk =====

## Each sample chunk points along its own axis: 7.4 along x, 7.5 along y, 1.4 along z
AXIS_VECTORS = numpy.array([
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0],
])


def stub_embedding(vector):
    """Stub: returns an embedding_function that gives the same vector for any question."""
    def embedding_function(question_text):
        return vector
    return embedding_function


# ===== Tests =====

def test_the_closest_direction_ranks_first():
    vector_search = VectorSearch(SAMPLE_CHUNKS, AXIS_VECTORS, stub_embedding([0.1, 0.9, 0.2]))
    results = vector_search.search("any question", top_k=3)
    assert [chunk["id"] for chunk in results] == ["laws-7.5", "laws-1.4", "laws-7.4"]


def test_a_longer_question_vector_ranks_the_same():
    """A longer question vector scales every dot product by the same amount, so the order stays."""
    short_search = VectorSearch(SAMPLE_CHUNKS, AXIS_VECTORS, stub_embedding([0.1, 0.9, 0.2]))
    long_search = VectorSearch(SAMPLE_CHUNKS, AXIS_VECTORS, stub_embedding([10.0, 90.0, 20.0]))
    short_ids = [chunk["id"] for chunk in short_search.search("any question", top_k=3)]
    long_ids = [chunk["id"] for chunk in long_search.search("any question", top_k=3)]
    assert short_ids == long_ids


def test_search_returns_top_k_chunks():
    vector_search = VectorSearch(SAMPLE_CHUNKS, AXIS_VECTORS, stub_embedding([1.0, 1.0, 1.0]))
    assert len(vector_search.search("any question", top_k=2)) == 2
