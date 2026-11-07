# 0006 · Vector search on clauses goes forward to Stage 2

- **Status:** Accepted
- **Date:** 2026-11-07
- **Stage:** 1, search types

## Context

Stage 1 compared keyword (BM25), vector and hybrid search (reciprocal rank fusion, k = 60) on three
chunkings: clauses, fixed windows and section groups (record 0001). Recall rose mostly with the
amount of text returned, so the search types were also compared at equal numbers of words.

## Options considered

1. **Vector search** (`mistral-embed`, exact search, record 0005).
2. **Hybrid search**, BM25 and vector fused by rank. The usual production default, because BM25
   catches exact terms such as clause numbers.
3. **Decide in Stage 2**, after answers are scored.

## Decision

Option 1: vector search on clauses. It leads or ties hybrid at every text size, needs one search
instead of two, and returns less text for the same recall.

## Evidence

Dev split, clauses, `search_text`:

| Words returned | Vector | Hybrid |
|---|---|---|
| About 170 (top 5) | 0.840 (160 words) | 0.771 (187 words) |
| About 400 (top 13) | 0.924 (403 words) | 0.847 (456 words) |
| About 1,550 | 0.979 (top 55) | 0.979 (top 50) |

Each gap alone is under the 2-question bar (rule 5), but the direction never changes: hybrid is
never ahead on clauses. Why, from the 4 questions where they differed at top 5: vector had the answer
at rank 3 to 5, and BM25 pushed keyword-only matches above it. BM25 is weak on short, paraphrased
matches (0.427 on paraphrased questions against vector's 0.823), and fusion weighs both lists equally.

Keyword search on clauses never came close (0.576 at top 5, 0.833 at about 1,550 words).

## Consequences

- **Easier:** one search, one embedding call per question, and a single knob for how much text the
  answer step reads: `top_k`.
- **Watch:** questions that name an exact term only BM25 would catch. None in the dev set failed
  that way, but the held-out set or real users might.
- **Open:** a weighted fusion (vector weighted above BM25) could still beat vector alone. Published
  work finds it beats plain rank fusion (Bruch, Gai and Ingber, ACM TOIS 2023,
  https://arxiv.org/abs/2210.11934). Not tested.
- **Next:** Stage 2 picks `top_k` by weighing answer quality against the words the model reads,
  since recall climbs from 0.840 (160 words) to 0.979 (about 1,550 words).
