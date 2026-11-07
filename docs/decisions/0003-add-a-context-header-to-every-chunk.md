# 0003 · Add a context header to every chunk's search text

- **Status:** Accepted
- **Date:** 2026-11-07
- **Stage:** 0, ingest; measured in Stage 1

## Context

A clause alone often lacks the words a question uses. "The whole shuttle shall be below 1.15
metres" never says "serve" or which rule book it comes from, so neither keyword nor vector search
can tell a Laws clause from an ITTO clause, or a Para Badminton clause from a standing one.

## Options considered

1. **Search the clause text alone.** Simplest, but loses the context above.
2. **Anthropic's Contextual Retrieval:** a model writes a short context for each chunk before
   embedding it. Anthropic reports fewer failed retrievals, at the cost of one model call per chunk.
   https://www.anthropic.com/engineering/contextual-retrieval
3. **The same idea without a model:** build the context from what the ingest already knows about
   each clause: document, format, Para flag, heading and clause number.

## Decision

Option 3. Every chunk gets `search_text`: a context header, a new line, then the clause, as in
`Laws of Badminton · 9. SERVICE · Clause 9.1.6`. Search reads `search_text`; answers still quote and
cite `text`, the clause as printed.

## Evidence

Stage 1, dev split, recall@5, the same search with and without the header:

| Search | Clause text alone | With the header |
|---|---|---|
| Keyword | 0.486 | 0.576 |
| Vector | 0.764 | 0.840 |
| Hybrid | 0.688 | 0.771 |

Each gain is about 2 questions, at the bar for a win (experiment rule 5).

## Consequences

- **Easier:** the header is free (no model call) and the same on every run.
- **Harder:** the header repeats across chunks, so chunks look more alike: the mean cosine
  similarity between two chunks rose from 0.757 to 0.818. It still helps on balance.
- **Watch:** `rank_bm25` gives any word found in more than half the chunks a minimum weight, so
  header words such as "clause" still score in BM25. Not yet tested.
