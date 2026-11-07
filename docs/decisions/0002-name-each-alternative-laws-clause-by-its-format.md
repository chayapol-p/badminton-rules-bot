# 0002 · Name each Alternative Laws clause by its format

- **Status:** Accepted
- **Date:** 2026-11-07
- **Stage:** 0, ingest

## Context

The Alternative Laws repeat the same clause numbers once per format: clause 8.1 exists in the
one-game-to-21 format and again in the best-of-5-games-to-11 format. Chunk ids built from the
document and clause number alone collided, so search results and citations could not
say which format a clause came from. The chunk field holding the format was first called `variant`,
which did not say what varies.

## Decision

Every chunk has an `alternative_format` field (empty for the Laws and the ITTO), and an Alternative
Laws chunk id carries its format: `alt-<format>:<clause>`, as in `alt-best-of-5-games-11:8.1`.
The field was renamed from `variant`, so its name says what varies: the format.

## Evidence

- 29 Alternative Laws chunks across 4 formats: best-of-5-games-11 (13), best-of-3-games-21 (11),
  one-game-21 (3), alternative-service (2). Every chunk id is unique (tested in
  `tests/test_rule_chunks.py`).
- Commit 1682684 renamed the field everywhere: chunks, rule links, golden questions and tests.

## Consequences

- **Easier:** a citation names the exact format, and the context header can say which format a
  clause belongs to (record 0003).
- **Watch:** a question that names no format should get the default Law first; the rule links handle
  that after search (`retrieval/expand_with_rule_links.py`).
