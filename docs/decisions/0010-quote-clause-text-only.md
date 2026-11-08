# 0010 · Quote only clause text, never a source's first line

- **Status:** Accepted (by experiment rule 5; Job delegated the runs on 8 Nov)
- **Date:** 2026-11-08
- **Stage:** 2 (answers, citations and refusals)

## Context
Each source block starts with a first line (document, version, in-force date, heading, clause), then
the clause text. Answers quote and cite the clause text (data rule 4). In run 1 the model quoted that
first line for two answers, and the citation check failed both: alternative-laws-in-force and
spin-serve-ban-date.

## Options considered
1. **Let the check accept the first line.** Breaks data rule 4: a version line isn't a rule.
2. **An answer rule:** quote only clause text; a fact found only in the first line is cited by
   chunk id, with clause words as the quote.

## Decision
Option 2, now standing answer rule 8.

## Evidence
`20261108T0904-top5` and `20261108T0912-top5-repeat`: 12 and 12 of 22, citations clean 0.971 and
0.914. `20261108T0921-top5-quote-clause-only`: 14 of 22, citations clean 1.0. Two questions apart.

## Consequences
The quote failures left are a different shape: quotes that skip words with "…" (itto-7.4 in three
runs). That needs its own decision: allow "…" between pieces that are each in the clause, or forbid it.
