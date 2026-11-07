# 0005 · Search the vectors exactly first: one dot product per chunk

- **Status:** Accepted
- **Date:** 2026-11-07
- **Stage:** 1, search types

## Context

Vector search compares the question's vector with the chunks' vectors. A vector database usually
adds an approximate index (such as HNSW in pgvector) that checks only part of the vectors, which
is faster at scale but can miss a few close ones.

## Options considered

1. **Exact search:** a dot product with every chunk's vector, in `numpy`, then sort.
2. **An approximate index (HNSW)**, as pgvector offers.

## Decision

Option 1 first. `mistral-embed` returns vectors of length 1, so the dot product is already the
cosine similarity. The move to pgvector, and maybe HNSW, comes later in the plan.

Why exact search first:

- It always finds the true closest chunks, so the eval measures the embeddings, not the index.
- 754 chunks of 1,024 numbers take well under a millisecond (about 0.04 ms), with no extra package.
- It is easy to test with hand-picked vectors, and gives the same ranking as FAISS's flat index.

## Evidence

- 3 tests in `tests/test_vector_search.py`.
- Vector search on clauses: recall@5 of 0.840 on the dev split, the best clause run so far.

## Consequences

- **Easier:** no index to tune, and results never depend on index settings.
- **Watch:** at hundreds of thousands of chunks, switch to an approximate index, and rerun the eval
  to show the score held.
