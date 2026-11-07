# 0004 · Use rank_bm25 for keyword search, and keep the class simple

- **Status:** Accepted
- **Date:** 2026-11-07
- **Stage:** 1, search types

## Context

Keyword search is the baseline every other search is compared with. Anthropic's course builds its
own BM25 index class with an `add_document` method, which also supports adding documents later.
Our corpus is fixed at 754 chunks, and nothing is added after ingest.

## Options considered

1. **Write a BM25 index class by hand, with `add_document`**, as in the course.
2. **Use the `rank_bm25` package**: `BM25Okapi` builds the index once from all chunks, and
   `get_top_n` returns the best chunks for a question.

## Decision

Option 2, kept simple first: `KeywordSearch(chunks, field)` tokenizes every chunk once, indexes it
with `BM25Okapi`, and `search()` returns `get_top_n(...)`. Adding documents later can come in a
refactor if the product ever needs it. The tokenizer keeps clause numbers such as `9.1.6` whole.

## Evidence

- 5 tests in `tests/test_keyword_search.py`.
- The baseline it set on the dev split: recall@5 of 0.576 on clauses (record 0003).

## Consequences

- **Easier:** less code to trust, and the scoring is the standard BM25 one.
- **Harder:** no adding chunks without rebuilding the index, which is fine for a fixed corpus.
- **Watch:** `rank_bm25`'s minimum weight for very common words (record 0003).
