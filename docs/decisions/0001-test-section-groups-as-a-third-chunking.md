# 0001 · Test section groups as a third chunking

- **Status:** Proposed (runs pending)
- **Date:** 2026-11-07
- **Stage:** 1, search types

## Context

Stage 1 compared keyword (BM25), vector and hybrid search on two chunkings: one chunk per
clause (median 22 words, 34 with the context header) and fixed windows of about 300 words.

| Run (dev, top 5) | recall@5 | Words returned |
|---|---|---|
| Vector, clauses | 0.840 | 160 |
| Hybrid, clauses | 0.771 | 187 |
| Keyword, clauses | 0.576 | 202 |
| Hybrid, windows | 0.875 | 1,583 |
| Vector, windows | 0.792 | 1,594 |
| Keyword, windows | 0.722 | 1,582 |

Two findings raised the chunking question:

- **Hybrid lost to vector on clauses** (about 1.7 questions, under the 2-question bar, but all
  4 differing questions went against hybrid). In each, vector had the answer at rank 3 to 5, and
  BM25 pushed keyword-only matches above it. Clauses are short, so a paraphrased question shares
  few exact words with them: BM25 scores 0.427 on paraphrased questions, vector 0.823.
- **Hybrid won on windows**, where BM25 has more words to match (0.722). But 5 windows hand the
  model about 10 times more text than 5 clauses, so part of that score is size.

Clauses alone also split rules that belong together: Law 9.1.6 (serve height) and its wheelchair
and standing-class variants 9.1.6.1 and 9.1.6.2 are three chunks. In 3 of the 13 dev questions
that need two or more locations, the locations sit in the same section.

## Options considered

1. **Keep one chunk per clause.** Precise matches and free citations, and the best vector score
   so far. Misses: BM25 is weak on short text, and related clauses are split.
2. **Fixed-size windows** (LangChain `RecursiveCharacterTextSplitter`, the usual baseline). Gives
   BM25 more words, but cuts across rules and returns far more text.
3. **Group by section (x.x), no size limit.** Follows the rule books' structure. Misses: sizes are
   very uneven, from one clause to ITTO 3.5 with 84 clauses and 2,497 words, and one vector for 84
   clauses blurs its meaning.
4. **Group by section (x.x), split under a word limit.** Section-aware chunking with a size cap, as
   in Unstructured's `by_title` strategy: a chunk never mixes two sections, and a hard maximum splits
   sections that are too big (https://docs.unstructured.io/api-reference/partition/chunking).
5. **Small-to-big at answer time** (LangChain's ParentDocumentRetriever, LlamaIndex's
   AutoMergingRetriever): search small pieces, hand the model their parent section. It changes what
   the model reads, not which clause search finds, so it belongs to Stage 2, not to this decision.

## Decision

Test option 4 as a third chunking in Stage 1: group each x.x clause with every clause under it,
and when a group passes 300 words, split it one level down (x.x.x), again if needed. The 300-word
limit matches the windows, so structure and fixed length compare at equal size.

The 754 clauses give 373 groups (median 36 words, none over 300). Code:
`retrieval/section_groups.py`, tested in `tests/test_section_groups.py`.

## Evidence

To run, one change each, on the dev split:

- [ ] `--search keyword --chunks sections`
- [ ] `--search vector --chunks sections` (after `scripts.build_embeddings` adds `section_groups`)
- [ ] `--search hybrid --chunks sections`

Accept if section groups beat clauses by 2 or more dev questions at a similar number of words
returned, or match windows with clearly fewer words. Otherwise reject, and keep clauses.

## Consequences

- **Easier:** related clauses arrive together, and BM25 gets more words per chunk.
- **Harder:** citations point to a group, so the answer step must still cite the exact clause
  inside it (each group lists the clauses it covers).
- **Watch:** small sections stay as single clauses (138 sections hold one clause). Merging small
  neighbours, Unstructured's `combine_text_under_n_chars`, is a possible next step if groups win.
