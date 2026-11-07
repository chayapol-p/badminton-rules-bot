"""
Vector search: ranks chunks by how close their meaning is to the question, using embeddings.

mistral-embed turns each text into 1,024 numbers. Texts with similar meaning point in
similar directions, so "What's the biggest a racket is allowed to be?" lands near "a frame
not exceeding 680 mm in overall length" even with few shared words. Closeness is cosine
similarity: how far two vectors point the same way, whatever their length.

Note: mistral-embed returns vectors of length 1 (Mistral's embeddings docs), so a plain dot
product already is the cosine similarity, and nothing needs scaling here. An embedding model
that does not do this would need every vector scaled to length 1 first.

This is exact search: the question is compared with every chunk, one dot product each.
Why that is the right first step here:
- It always finds the true closest chunks, so the eval measures the embeddings, not the index.
- 754 chunks take well under a millisecond, with numpy alone and no extra package.
- It is easy to test with hand-picked vectors, and gives the same ranking as FAISS's flat index.
At hundreds of thousands of chunks, teams switch to an approximate index such as HNSW
(pgvector supports it), which checks only part of the vectors and can miss a few close ones.

The question's vector comes from embedding_function, a function passed in, so the eval can
pass saved vectors and the product can pass a live API call, without changing this class.

Use:
    vector_search = VectorSearch(chunks, chunk_vectors, embedding_function)
    results = vector_search.search("How tall are the posts?", top_k=5)
"""

from collections.abc import Callable

import numpy


# ===== The search =====

class VectorSearch:
    """Ranks chunks by cosine similarity between the question's vector and each chunk's vector."""

    def __init__(
        self,
        chunks: list[dict],
        chunk_vectors: numpy.ndarray,
        embedding_function: Callable[[str], list[float] | numpy.ndarray],
    ):
        # One row of chunk_vectors per chunk, in the same order as chunks
        self.chunks = chunks
        self.chunk_vectors = chunk_vectors
        self.embedding_function = embedding_function

    def search(self, question_text: str, top_k: int) -> list[dict]:
        """Returns the top_k chunks whose vectors are closest to the question's vector."""
        # Embed the question
        question_vector = self.embedding_function(question_text)

        # One cosine similarity per chunk: the dot product of length-1 vectors
        similarities = numpy.dot(self.chunk_vectors, question_vector)

        # Most similar first, with a stable sort so ties keep ingest order
        best_positions = numpy.argsort(-similarities, kind="stable")[:top_k]

        return [self.chunks[position] for position in best_positions]
